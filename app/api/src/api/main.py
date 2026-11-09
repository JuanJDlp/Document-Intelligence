import hashlib
import logging
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import UUID, uuid4
from typing import Any, AsyncIterator, Mapping
from sqlalchemy.engine import Engine
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, insert, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException
from receipt_engine import DocumentError, DocumentInput, DocumentValidator, EngineSettings
from .db import now, production_engine, sessions, users
from .documents import DynamoDocuments
from .settings import ApiSettings

logger = logging.getLogger(__name__)
hasher = PasswordHasher()
dummy_hash = hasher.hash("TimingEqualityPassword123")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class Registration(Credentials):
    full_name: str = Field(min_length=1, max_length=200)


class RoleChange(BaseModel):
    role: str


def public_user(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **{k: row[k] for k in ("id", "email", "full_name", "role")},
        "created_at": row["created_at"].isoformat(timespec="milliseconds") + "Z",
    }


def validate_identity(email: str, password: str, name: str) -> str:
    email = email.strip().lower()
    if (
        not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        or not 12 <= len(password) <= 128
        or not re.search(r"[A-Za-z]", password)
        or not re.search(r"[0-9]", password)
        or not name.strip()
    ):
        raise ApiError(400, "VALIDATION_ERROR", "Invalid registration fields.")
    return email


def create_app(database: Engine | None = None, documents: DynamoDocuments | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if database is None:
            application.state.database = production_engine()
        settings = ApiSettings.from_environment(require_aws=documents is None)
        application.state.settings = settings
        if documents is None:
            application.state.documents = DynamoDocuments(
                region=settings.region,
                bucket=settings.bucket,
                documents=settings.documents_table,
                jobs=settings.jobs_table,
            )
        yield
        if database is None:
            application.state.database.dispose()

    application = FastAPI(title="DocuProcess API", version="1.0.0", lifespan=lifespan)
    application.state.database = database
    application.state.documents = documents
    origin = os.environ.get("DOCUPROCESS_CORS_ORIGIN")
    if origin:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=[origin],
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @application.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message, "details": {}}},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return await api_error(
            request, ApiError(400, "VALIDATION_ERROR", "Invalid request fields.")
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return await api_error(
            request,
            ApiError(
                exc.status_code,
                "NOT_FOUND" if exc.status_code == 404 else "VALIDATION_ERROR",
                "Request not available.",
            ),
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("event=request.failed exception_class=%s", type(exc).__name__)
        return await api_error(
            request, ApiError(500, "INTERNAL_ERROR", "Request could not be completed.")
        )

    def current_user(request: Request) -> dict[str, Any]:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or len(header) > 512:
            raise ApiError(401, "UNAUTHENTICATED", "Authentication required.")
        hashed = hashlib.sha256(header[7:].encode()).hexdigest()
        with application.state.database.connect() as connection:
            row = (
                connection.execute(
                    select(users)
                    .join(sessions)
                    .where(
                        sessions.c.token_hash == hashed,
                        sessions.c.revoked_at.is_(None),
                        sessions.c.expires_at > now(),
                    )
                )
                .mappings()
                .first()
            )
        if not row:
            raise ApiError(401, "UNAUTHENTICATED", "Authentication required.")
        return dict(row)

    def admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["role"] != "admin":
            raise ApiError(403, "FORBIDDEN", "Administrator access required.")
        return user

    @application.post("/api/v1/auth/register", status_code=201)
    def register(body: Registration) -> dict[str, Any]:
        email = validate_identity(body.email, body.password, body.full_name)
        row = {
            "id": str(uuid4()),
            "email": email,
            "password_hash": hasher.hash(body.password),
            "full_name": body.full_name.strip(),
            "role": "user",
            "created_at": now(),
            "updated_at": now(),
        }
        try:
            with application.state.database.begin() as connection:
                connection.execute(insert(users).values(**row))
        except IntegrityError:
            raise ApiError(409, "CONFLICT", "Email already registered.") from None
        return public_user(row)

    @application.post("/api/v1/auth/login")
    def login(body: Credentials) -> dict[str, str]:
        with application.state.database.connect() as connection:
            row = (
                connection.execute(select(users).where(users.c.email == body.email.strip().lower()))
                .mappings()
                .first()
            )
        valid: bool = False
        try:
            valid = hasher.verify(row["password_hash"] if row else dummy_hash, body.password)
        except (VerificationError, InvalidHashError):
            valid = False
        if not valid or not row:
            raise ApiError(401, "UNAUTHENTICATED", "Invalid credentials.")
        token, time = secrets.token_urlsafe(32), now()
        expiry = time + timedelta(hours=8)
        with application.state.database.begin() as connection:
            connection.execute(
                insert(sessions).values(
                    id=str(uuid4()),
                    user_id=row["id"],
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    created_at=time,
                    expires_at=expiry,
                )
            )
        return {"token": token, "expires_at": expiry.isoformat(timespec="milliseconds") + "Z"}

    @application.post("/api/v1/auth/logout", status_code=204)
    def logout(request: Request, user: dict[str, Any] = Depends(current_user)) -> Response:
        hashed = hashlib.sha256(request.headers["Authorization"][7:].encode()).hexdigest()
        with application.state.database.begin() as connection:
            connection.execute(
                update(sessions).where(sessions.c.token_hash == hashed).values(revoked_at=now())
            )
        return Response(status_code=204)

    @application.get("/api/v1/me")
    def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        return public_user(user)

    @application.post("/api/v1/documents", status_code=202)
    async def upload(
        file: UploadFile = File(...), user: dict[str, Any] = Depends(current_user)
    ) -> dict[str, Any]:
        max_size = application.state.settings.max_upload_bytes
        try:
            content = await file.read(max_size + 1)
        finally:
            await file.close()
        if len(content) > max_size:
            raise ApiError(413, "DOCUMENT_TOO_LARGE", "File exceeds 5 MiB.")
        try:
            mime, _ = DocumentValidator(EngineSettings(max_document_bytes=max_size)).validate(
                DocumentInput(str(uuid4()), content, file.content_type, file.filename)
            )
        except DocumentError as exc:
            if exc.code == "UNSUPPORTED_FORMAT":
                raise ApiError(
                    415, "UNSUPPORTED_MEDIA_TYPE", "Unsupported document format."
                ) from None
            raise ApiError(
                422, "INVALID_DOCUMENT", "Invalid or unsupported document contents."
            ) from None
        created = application.state.documents.create(
            user["id"], file.filename or "document", mime, content
        )
        logger.info(
            "event=document.accepted document_id=%s job_id=%s",
            created["document_id"],
            created["job_id"],
        )
        return created

    @application.get("/api/v1/documents")
    def listing(
        limit: int = Query(20, ge=1, le=100),
        cursor: str | None = None,
        user_id: str | None = None,
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        scope = user_id if user["role"] == "admin" else user["id"]
        try:
            return application.state.documents.list(scope, limit, cursor)
        except (ValueError, KeyError):
            raise ApiError(400, "VALIDATION_ERROR", "Invalid pagination cursor.") from None

    @application.get("/api/v1/documents/{document_id}")
    def detail(document_id: UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        item = application.state.documents.get(str(document_id))
        if not item or (item["user_id"] != user["id"] and user["role"] != "admin"):
            raise ApiError(404, "NOT_FOUND", "Document not found.")
        return application.state.documents.public(item)

    @application.get("/api/v1/admin/users")
    def list_users(
        limit: int = Query(20, ge=1, le=100),
        cursor: str | None = None,
        user: dict[str, Any] = Depends(admin),
    ) -> dict[str, Any]:
        import base64
        import json

        query = select(users).order_by(users.c.created_at, users.c.id).limit(limit + 1)
        if cursor:
            try:
                boundary = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                from datetime import datetime

                created = datetime.fromisoformat(boundary[0])
                query = query.where(
                    or_(
                        users.c.created_at > created,
                        and_(users.c.created_at == created, users.c.id > boundary[1]),
                    )
                )
            except (ValueError, KeyError, IndexError, TypeError):
                raise ApiError(400, "VALIDATION_ERROR", "Invalid pagination cursor.") from None
        with application.state.database.connect() as connection:
            rows = connection.execute(query).mappings().all()
        more = len(rows) > limit
        rows = rows[:limit]
        token = (
            base64.urlsafe_b64encode(
                json.dumps([rows[-1]["created_at"].isoformat(), rows[-1]["id"]]).encode()
            ).decode()
            if more
            else None
        )
        return {"items": [public_user(row) for row in rows], "next_cursor": token}

    @application.patch("/api/v1/admin/users/{user_id}/role")
    def set_role(
        user_id: UUID, body: RoleChange, user: dict[str, Any] = Depends(admin)
    ) -> dict[str, Any]:
        if body.role not in ("user", "admin"):
            raise ApiError(400, "VALIDATION_ERROR", "Invalid role.")
        if str(user_id) == user["id"]:
            raise ApiError(409, "CONFLICT", "Changing your own role is not allowed.")
        with application.state.database.begin() as connection:
            changed = connection.execute(
                update(users)
                .where(users.c.id == str(user_id))
                .values(role=body.role, updated_at=now())
            )
            if changed.rowcount == 0:
                raise ApiError(404, "NOT_FOUND", "User not found.")
        return {"id": str(user_id), "role": body.role}

    @application.get("/api/v1/health")
    def health() -> Any:
        try:
            with application.state.database.connect() as connection:
                connection.execute(text("SELECT 1"))
            application.state.documents.health()
        except Exception:
            return JSONResponse({"status": "degraded"}, status_code=503)
        return {"status": "ok"}

    return application


app = create_app()
