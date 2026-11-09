"""Local-only interactive demo: in-process AWS mocks, temporary SQLite, real OCR."""

import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import boto3
    import uvicorn
    from moto import mock_aws
    from sqlalchemy import create_engine
    from fastapi.staticfiles import StaticFiles
    from api.db import metadata
    from api.documents import DynamoDocuments
    from api.main import create_app
    from worker.main import Worker
    from worker.store import JobStore

    # Fake credentials only for the in-process moto environment, never persisted.
    os.environ.update(
        AWS_ACCESS_KEY_ID="testing",
        AWS_SECRET_ACCESS_KEY="testing",
        AWS_SESSION_TOKEN="testing",
        AWS_DEFAULT_REGION="us-east-1",
        AWS_EC2_METADATA_DISABLED="true",
    )
    with mock_aws(), tempfile.TemporaryDirectory() as folder:
        region = "us-east-1"
        boto3.client("s3", region_name=region).create_bucket(Bucket="docuprocess-local-uploads")
        dynamodb = boto3.client("dynamodb", region_name=region)
        for name, key, index, partition, sort in [
            ("local-documents", "document_id", "gsi_user_created", "user_id", "created_at"),
            ("local-jobs", "job_id", "gsi_status_available", "status", "available_at"),
        ]:
            dynamodb.create_table(
                TableName=name,
                BillingMode="PAY_PER_REQUEST",
                KeySchema=[{"AttributeName": key, "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": k, "AttributeType": "S"} for k in (key, partition, sort)
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": index,
                        "KeySchema": [
                            {"AttributeName": partition, "KeyType": "HASH"},
                            {"AttributeName": sort, "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
            )
        topic = boto3.client("sns", region_name=region).create_topic(Name="local-notifications")[
            "TopicArn"
        ]
        engine = create_engine(
            "sqlite:///" + str(Path(folder) / "users.db"), connect_args={"check_same_thread": False}
        )
        metadata.create_all(engine)
        docs = DynamoDocuments(
            region=region,
            bucket="docuprocess-local-uploads",
            documents="local-documents",
            jobs="local-jobs",
        )
        application = create_app(engine, docs)
        application.mount(
            "/", StaticFiles(directory=ROOT / "app/frontend", html=True), name="frontend"
        )
        store = JobStore(
            region=region,
            bucket="docuprocess-local-uploads",
            documents="local-documents",
            jobs="local-jobs",
            topic=topic,
        )
        worker = Worker(store)
        thread = threading.Thread(target=worker.run, daemon=True)
        thread.start()
        print("Local demo: http://127.0.0.1:8000 — AWS mocked; all data resets on exit.")
        try:
            uvicorn.run(application, host="127.0.0.1", port=8000, access_log=False)
        finally:
            worker.shutdown.set()
            thread.join(timeout=65)
            engine.dispose()


if __name__ == "__main__":
    main()
