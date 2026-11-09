from datetime import timedelta
from sqlalchemy import select, update
from api.db import now, sessions, users


def register(client, email="other@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123", "full_name": "Synthetic User"},
    )


def test_api_auth_register_and_duplicate(api_client):
    client = api_client.client
    response = register(client, "  Mixed@Example.com ")
    assert response.status_code == 201
    assert response.json()["email"] == "mixed@example.com"
    assert "password_hash" not in response.text
    assert register(client, "mixed@example.com").status_code == 409


def test_api_auth_validation(api_client):
    for password in ("short", "nonumbershere", "1234567890123"):
        assert (
            api_client.client.post(
                "/api/v1/auth/register",
                json={"email": "valid@example.com", "password": password, "full_name": "Test"},
            ).status_code
            == 400
        )
    assert register(api_client.client, "bad-email").status_code == 400


def test_api_auth_wrong_password_and_unknown_user(api_client):
    register(api_client.client)
    responses = [
        api_client.client.post(
            "/api/v1/auth/login", json={"email": email, "password": "WrongPassword123"}
        )
        for email in ("other@example.com", "missing@example.com")
    ]
    assert responses[0].status_code == responses[1].status_code == 401
    assert responses[0].json() == responses[1].json()


def test_api_auth_hashes_and_logout(api_client, identity):
    client = api_client.client
    token = client.headers["Authorization"][7:]
    assert client.get("/api/v1/me").status_code == 200
    with api_client.engine.connect() as conn:
        assert conn.execute(select(sessions.c.token_hash)).scalar() != token
        assert conn.execute(select(users.c.password_hash)).scalar().startswith("$argon2id$")
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/me").status_code == 401


def test_api_auth_expired(api_client, identity):
    with api_client.engine.begin() as conn:
        conn.execute(update(sessions).values(expires_at=now() - timedelta(seconds=1)))
    assert api_client.client.get("/api/v1/me").status_code == 401


def test_api_doc_invalid_uploads(api_client, identity):
    for data, mime, code in [
        (b"notpdf", "application/pdf", 415),
        (b"", "application/pdf", 422),
        (b"%PDF-broken", "application/pdf", 422),
        (b"x" * 5242881, "image/png", 413),
    ]:
        response = api_client.client.post(
            "/api/v1/documents", files={"file": ("file.pdf", data, mime)}
        )
        assert response.status_code == code
        assert "error" in response.json()


def test_api_doc_owner_security(api_client, identity, image_bytes):
    first = api_client.client
    uploaded = first.post(
        "/api/v1/documents", files={"file": ("../synthetic.png", image_bytes, "image/png")}
    )
    assert uploaded.status_code == 202
    doc = uploaded.json()["document_id"]
    assert "s3_key" not in first.get("/api/v1/documents/" + doc).text
    register(first)
    token = first.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "SecurePassword123"}
    ).json()["token"]
    first.headers["Authorization"] = "Bearer " + token
    assert first.get("/api/v1/documents/" + doc).status_code == 404
    assert first.get("/api/v1/documents").json()["items"] == []


def test_api_doc_pagination(api_client, identity, image_bytes):
    for _ in range(3):
        assert (
            api_client.client.post(
                "/api/v1/documents", files={"file": ("test.png", image_bytes, "image/png")}
            ).status_code
            == 202
        )
    page = api_client.client.get("/api/v1/documents?limit=2").json()
    assert len(page["items"]) == 2
    second = api_client.client.get(
        "/api/v1/documents", params={"limit": 2, "cursor": page["next_cursor"]}
    ).json()
    assert len(second["items"]) == 1
    assert page["items"][0]["document_id"] != second["items"][0]["document_id"]
    assert api_client.client.get("/api/v1/documents?cursor=bad").status_code == 400


def test_api_adm_permissions_and_self_demotion(api_client, identity):
    client = api_client.client
    assert client.get("/api/v1/admin/users").status_code == 403
    with api_client.engine.begin() as conn:
        conn.execute(update(users).where(users.c.id == identity["id"]).values(role="admin"))
    assert client.get("/api/v1/admin/users").status_code == 200
    assert (
        client.patch(
            "/api/v1/admin/users/" + identity["id"] + "/role", json={"role": "user"}
        ).status_code
        == 409
    )
    other = register(client).json()
    assert (
        client.patch(
            "/api/v1/admin/users/" + other["id"] + "/role", json={"role": "admin"}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/admin/users?limit=1").json()["next_cursor"]


def test_api_ops_health(api_client, aws_services, monkeypatch):
    assert api_client.client.get("/api/v1/health").json() == {"status": "ok"}

    def fail():
        raise RuntimeError()

    monkeypatch.setattr(aws_services.docs, "health", fail)
    assert api_client.client.get("/api/v1/health").status_code == 503


def test_api_doc_compensation(api_client, identity, aws_services, image_bytes, monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(aws_services.docs.jobs, "put_item", fail)
    assert (
        api_client.client.post(
            "/api/v1/documents", files={"file": ("test.png", image_bytes, "image/png")}
        ).status_code
        == 500
    )
    assert aws_services.docs.documents.scan()["Count"] == 0
    assert (
        aws_services.docs.s3.list_objects_v2(Bucket=aws_services.docs.bucket).get("KeyCount", 0)
        == 0
    )
