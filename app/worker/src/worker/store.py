"""AWS adapters. Every state/mirror transition uses an atomic conditional transaction."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

TERMINAL = {"COMPLETED", "PARTIAL", "FAILED"}


def stamp(time: datetime) -> str:
    return time.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class JobStore:
    def __init__(self, *, region: str, bucket: str, documents: str, jobs: str, topic: str) -> None:
        self.s3 = boto3.client("s3", region_name=region)
        self.ddb = boto3.resource("dynamodb", region_name=region)
        self.documents = self.ddb.Table(documents)
        self.jobs = self.ddb.Table(jobs)
        # An independent low-level client avoids the resource's serialization hooks.
        self.client = boto3.client("dynamodb", region_name=region)
        self.sns = boto3.client("sns", region_name=region)
        self.bucket, self.topic = bucket, topic

    def poll(self, time: datetime) -> list[dict[str, Any]]:
        items = []
        for status in ("PENDING", "RUNNING"):
            items.extend(
                self.jobs.query(
                    IndexName="gsi_status_available",
                    KeyConditionExpression=Key("status").eq(status)
                    & Key("available_at").lte(stamp(time)),
                    Limit=10,
                )["Items"]
            )
        return items

    def document(self, document_id: str) -> dict[str, Any] | None:
        return self.documents.get_item(Key={"document_id": document_id}, ConsistentRead=True).get(
            "Item"
        )

    def transition(
        self,
        old: dict[str, Any],
        new: dict[str, Any],
        time: datetime,
        *,
        require_live: bool = False,
    ) -> bool:
        encode = TypeSerializer().serialize

        def compatible(value: Any) -> Any:
            if isinstance(value, float):
                return Decimal(str(value))
            if isinstance(value, dict):
                return {k: compatible(v) for k, v in value.items()}
            if isinstance(value, list):
                return [compatible(v) for v in value]
            return value

        def item(value: dict[str, Any]) -> dict[str, Any]:
            return {k: encode(compatible(v)) for k, v in value.items()}

        expression = "#s=:s AND available_at=:a AND attempts=:n"
        values = {":s": old["status"], ":a": old["available_at"], ":n": old["attempts"]}
        if old["status"] == "RUNNING":
            expression += " AND lease_owner=:owner"
            values[":owner"] = old["lease_owner"]
        if require_live:
            expression += " AND available_at>:now"
            values[":now"] = stamp(time)
        operations = [
            {
                "Put": {
                    "TableName": self.jobs.name,
                    "Item": item(new),
                    "ConditionExpression": expression,
                    "ExpressionAttributeNames": {"#s": "status"},
                    "ExpressionAttributeValues": item(values),
                }
            }
        ]
        document = self.document(old["document_id"])
        if document:
            mirror = {
                "processing_status": new["status"],
                "processing_attempts": int(new["attempts"]),
                "processing_updated_at": new["updated_at"],
                "updated_at": new["updated_at"],
            }
            if new.get("last_error_code"):
                mirror["processing_last_error_code"] = new["last_error_code"]
            if new["status"] in TERMINAL and new.get("result") is not None:
                mirror["result"] = new["result"]
            names = {f"#k{i}": key for i, key in enumerate(mirror)}
            values = {f":v{i}": value for i, value in enumerate(mirror.values())}
            update_expression = "SET " + ", ".join(f"#k{i}=:v{i}" for i in range(len(mirror)))
            if not new.get("last_error_code"):
                update_expression += " REMOVE processing_last_error_code"
            operations.append(
                {
                    "Update": {
                        "TableName": self.documents.name,
                        "Key": item({"document_id": old["document_id"]}),
                        "UpdateExpression": update_expression,
                        "ConditionExpression": "attribute_exists(document_id)",
                        "ExpressionAttributeNames": names,
                        "ExpressionAttributeValues": item(values),
                    }
                }
            )
        # Results belong to documents, not the queue record.
        operations[0]["Put"]["Item"].pop("result", None)
        try:
            self.client.transact_write_items(TransactItems=operations)
            return True
        except ClientError as exc:
            reasons = exc.response.get("CancellationReasons", [])
            if exc.response["Error"]["Code"] == "TransactionCanceledException" and any(
                r.get("Code") == "ConditionalCheckFailed" for r in reasons
            ):
                return False
            raise

    def read_bytes(self, key: str, limit: int) -> bytes:
        info = self.s3.head_object(Bucket=self.bucket, Key=key)
        if info["ContentLength"] > limit:
            raise OversizeDocument()
        stream = self.s3.get_object(Bucket=self.bucket, Key=key)["Body"]
        try:
            data = stream.read(limit + 1)
        finally:
            stream.close()
        if len(data) > limit:
            raise OversizeDocument()
        return data

    def publish(self, job: dict[str, Any], time: datetime) -> None:
        message = {
            "event": "document.processing.finished",
            "document_id": job["document_id"],
            "job_id": job["job_id"],
            "status": job["status"],
            "occurred_at": stamp(time),
        }
        self.sns.publish(
            TopicArn=self.topic,
            Message=json.dumps(message),
            MessageAttributes={"status": {"DataType": "String", "StringValue": job["status"]}},
        )

    def record_notification(self, job: dict[str, Any], state: str, time: datetime) -> None:
        self.jobs.update_item(
            Key={"job_id": job["job_id"]},
            UpdateExpression=(
                "SET notification_status=:n, notified_at=:t"
                if state == "SENT"
                else "SET notification_status=:n REMOVE notified_at"
            ),
            ConditionExpression="#s=:s AND attempts=:a",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":n": state,
                **({":t": stamp(time)} if state == "SENT" else {}),
                ":s": job["status"],
                ":a": job["attempts"],
            },
        )


class OversizeDocument(Exception):
    pass
