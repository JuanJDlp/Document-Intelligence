"""API-DOC-02/03 and API-DOC-05: invalid inputs and opaque cursor validation."""

import base64
import json
from pathlib import Path
import pytest

SAMPLES = Path(__file__).resolve().parents[3] / "samples/receipts"


@pytest.mark.parametrize("name", ["encrypted.pdf", "multipage.pdf"])
def test_api_doc_unprocessable_pdf(api_client, identity, name):
    response = api_client.client.post(
        "/api/v1/documents",
        files={"file": (name, (SAMPLES / name).read_bytes(), "application/pdf")},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"document_id": []},
        {"user_id": "different", "created_at": "2026-01-01", "document_id": "id"},
    ],
)
def test_api_doc_invalid_cursor_structure(api_client, identity, value):
    cursor = base64.urlsafe_b64encode(json.dumps(value).encode()).decode()
    assert api_client.client.get("/api/v1/documents", params={"cursor": cursor}).status_code == 400
