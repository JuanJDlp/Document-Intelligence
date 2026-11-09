import base64
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4
import boto3
from boto3.dynamodb.conditions import Key


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


class DynamoDocuments:
    def __init__(self, *, region: str, bucket: str, documents: str, jobs: str) -> None:
        self.s3 = boto3.client("s3", region_name=region)
        db = boto3.resource("dynamodb", region_name=region)
        self.documents = db.Table(documents)
        self.jobs = db.Table(jobs)
        self.bucket = bucket

    def health(self) -> None:
        self.documents.get_item(Key={"document_id": "__health__"}, ConsistentRead=True)

    def create(self, user_id: str, filename: str, mime: str, content: bytes) -> dict[str, Any]:
        document_id, job_id, time = str(uuid4()), str(uuid4()), timestamp()
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:100] or "document"
        key = f"uploads/{user_id}/{document_id}/{safe}"
        document = {
            "document_id": document_id,
            "job_id": job_id,
            "user_id": user_id,
            "filename": safe,
            "mime_type": mime,
            "size_bytes": len(content),
            "s3_key": key,
            "created_at": time,
            "updated_at": time,
            "processing_status": "PENDING",
            "processing_attempts": 0,
            "processing_updated_at": time,
        }
        job = {
            "job_id": job_id,
            "document_id": document_id,
            "status": "PENDING",
            "available_at": time,
            "attempts": 0,
            "max_attempts": 3,
            "created_at": time,
            "updated_at": time,
        }
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=mime)
        try:
            self.documents.put_item(
                Item=document, ConditionExpression="attribute_not_exists(document_id)"
            )
            self.jobs.put_item(Item=job, ConditionExpression="attribute_not_exists(job_id)")
        except Exception:
            self.documents.delete_item(Key={"document_id": document_id})
            self.s3.delete_object(Bucket=self.bucket, Key=key)
            raise
        return {
            "document_id": document_id,
            "job_id": job_id,
            "status": "PENDING",
            "filename": safe,
            "mime_type": mime,
            "size_bytes": len(content),
            "created_at": time,
        }

    @staticmethod
    def public(item: dict[str, Any]) -> dict[str, Any]:
        return plain(
            {
                k: item[k]
                for k in ("document_id", "filename", "mime_type", "size_bytes", "created_at")
            }
        ) | {
            "processing": {
                "status": item["processing_status"],
                "attempts": int(item.get("processing_attempts", 0)),
                "last_error_code": item.get("processing_last_error_code"),
                "updated_at": item.get("processing_updated_at", item["updated_at"]),
            },
            "result": plain(item.get("result")),
        }

    def get(self, document_id: str) -> dict[str, Any] | None:
        return self.documents.get_item(Key={"document_id": document_id}, ConsistentRead=True).get(
            "Item"
        )

    def list(self, user_id: str | None, limit: int, cursor: str | None) -> dict[str, Any]:
        start = None
        if cursor:
            if len(cursor) > 4096:
                raise ValueError("Invalid cursor")
            try:
                start = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                required = (
                    {"user_id", "created_at", "document_id"}
                    if user_id is not None
                    else {"created_at", "document_id"}
                )
                if (
                    not isinstance(start, dict)
                    or set(start) != required
                    or not all(isinstance(v, str) and v for v in start.values())
                ):
                    raise ValueError()
                if user_id is not None and start["user_id"] != user_id:
                    raise ValueError()
            except (ValueError, UnicodeError):
                raise ValueError("Invalid cursor") from None
        if user_id is not None:
            args: dict[str, Any] = {
                "IndexName": "gsi_user_created",
                "KeyConditionExpression": Key("user_id").eq(user_id),
                "ScanIndexForward": False,
                "Limit": limit,
            }
            if start:
                args["ExclusiveStartKey"] = start
            page = self.documents.query(**args)
            items, end = page["Items"], page.get("LastEvaluatedKey")
        else:
            # Admin-only scan is intentionally limited to sandbox-scale data.
            page = self.documents.scan()
            items = page["Items"]
            while page.get("LastEvaluatedKey"):
                page = self.documents.scan(ExclusiveStartKey=page["LastEvaluatedKey"])
                items.extend(page["Items"])
            items.sort(key=lambda x: (x["created_at"], x["document_id"]), reverse=True)
            if start:
                boundary = (start["created_at"], start["document_id"])
                items = [x for x in items if (x["created_at"], x["document_id"]) < boundary]
            more = len(items) > limit
            items = items[:limit]
            end = {k: items[-1][k] for k in ("created_at", "document_id")} if more else None
        token = base64.urlsafe_b64encode(json.dumps(end).encode()).decode() if end else None
        return {"items": [self.public(item) for item in items], "next_cursor": token}
