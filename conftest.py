from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
import boto3
import pytest
from moto import mock_aws
from PIL import Image
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from api.db import metadata
from api.documents import DynamoDocuments
from api.main import create_app
from receipt_engine import DocumentInput, OcrLine, OcrResult, ReceiptExtractionEngine
from worker.main import Worker
from worker.store import JobStore


class Clock:
    def __init__(self):
        self.time = datetime(2026, 1, 16, tzinfo=timezone.utc)

    def __call__(self):
        return self.time


class FakeOcr:
    name = "fake"

    def __init__(self, lines=None):
        self.lines = (
            lines
            if lines is not None
            else [
                "SYNTHETIC MARKET",
                "FACTURA No INV-001",
                "NIT 900123456-8",
                "FECHA: 15/01/2026",
                "SUBTOTAL: COP 100.000",
                "IVA: COP 19.000",
                "TOTAL: COP 119.000",
                "EFECTIVO",
            ]
        )

    def extract(self, request):
        return OcrResult(tuple(OcrLine(line, 0.9) for line in self.lines), self.name)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def image_bytes():
    stream = BytesIO()
    Image.new("RGB", (100, 100), "white").save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def aws_services(monkeypatch, clock):
    for key, value in {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_EC2_METADATA_DISABLED": "true",
    }.items():
        monkeypatch.setenv(key, value)
    from worker.store import stamp

    monkeypatch.setattr("api.documents.timestamp", lambda: stamp(clock.time))
    with mock_aws():
        region = "us-east-1"
        s3 = boto3.client("s3", region_name=region)
        s3.create_bucket(Bucket="synthetic-uploads")
        db = boto3.client("dynamodb", region_name=region)
        for name, pk, index, index_pk, index_sk in [
            ("synthetic-documents", "document_id", "gsi_user_created", "user_id", "created_at"),
            ("synthetic-jobs", "job_id", "gsi_status_available", "status", "available_at"),
        ]:
            db.create_table(
                TableName=name,
                BillingMode="PAY_PER_REQUEST",
                KeySchema=[{"AttributeName": pk, "KeyType": "HASH"}],
                AttributeDefinitions=[
                    {"AttributeName": key, "AttributeType": "S"} for key in (pk, index_pk, index_sk)
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": index,
                        "KeySchema": [
                            {"AttributeName": index_pk, "KeyType": "HASH"},
                            {"AttributeName": index_sk, "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
            )
        topic = boto3.client("sns", region_name=region).create_topic(Name="synthetic-processing")[
            "TopicArn"
        ]
        docs = DynamoDocuments(
            region=region,
            bucket="synthetic-uploads",
            documents="synthetic-documents",
            jobs="synthetic-jobs",
        )
        store = JobStore(
            region=region,
            bucket="synthetic-uploads",
            documents="synthetic-documents",
            jobs="synthetic-jobs",
            topic=topic,
        )
        messages = []
        publish = store.sns.publish

        def capture(**kwargs):
            messages.append(kwargs)
            return publish(**kwargs)

        monkeypatch.setattr(store.sns, "publish", capture)

        def processor(content, mime, document_id, shutdown=None):
            return (
                ReceiptExtractionEngine(ocr_provider=FakeOcr(), clock=clock)
                .process(DocumentInput(document_id, content, mime))
                .to_dict()
            )

        worker = Worker(store, clock=clock, processor=processor, sleep=lambda _: None)
        yield SimpleNamespace(docs=docs, store=store, worker=worker, messages=messages)


@pytest.fixture
def api_client(aws_services):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def enable_fk(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    metadata.create_all(engine)
    application = create_app(engine, aws_services.docs)
    with TestClient(application, raise_server_exceptions=False) as client:
        yield SimpleNamespace(client=client, engine=engine, app=application)
    engine.dispose()


@pytest.fixture
def identity(api_client):
    client = api_client.client
    body = {
        "email": "person@example.com",
        "password": "SecurePassword123",
        "full_name": "Synthetic User",
    }
    user = client.post("/api/v1/auth/register", json=body).json()
    token = client.post("/api/v1/auth/login", json=body).json()["token"]
    client.headers["Authorization"] = "Bearer " + token
    return user
