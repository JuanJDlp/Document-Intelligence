from datetime import datetime, timezone
import json


def test_tst_e2e_offline_flow(api_client, identity, aws_services, image_bytes, clock, caplog):
    client = api_client.client
    clock.time = datetime.now(timezone.utc)
    with caplog.at_level("INFO"):
        upload = client.post(
            "/api/v1/documents", files={"file": ("private-fixture.png", image_bytes, "image/png")}
        )
        assert upload.status_code == 202
        document_id = upload.json()["document_id"]
        assert (
            client.get("/api/v1/documents/" + document_id).json()["processing"]["status"]
            == "PENDING"
        )
        assert aws_services.worker.run_once()
        detail = client.get("/api/v1/documents/" + document_id).json()
        assert detail["processing"]["status"] == "COMPLETED"
        assert detail["result"]["extracted_data"]["total"] == "119000.00"
        assert len(aws_services.messages) == 1
        assert json.loads(aws_services.messages[0]["Message"])["document_id"] == document_id
        assert client.post("/api/v1/auth/logout").status_code == 204
        assert client.get("/api/v1/documents/" + document_id).status_code == 401
    for value in (
        "private-fixture.png",
        "SYNTHETIC MARKET",
        "SecurePassword123",
        "person@example.com",
        "119000.00",
    ):
        assert value not in caplog.text
