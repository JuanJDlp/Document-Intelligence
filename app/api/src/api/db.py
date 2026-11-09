import os
from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    create_engine,
)
from sqlalchemy.engine import Engine, URL

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("password_hash", String(255), nullable=False),
    Column("full_name", String(200), nullable=False),
    Column("role", String(10), nullable=False),
    CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)
sessions = Table(
    "sessions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("token_hash", String(64), unique=True, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("expires_at", DateTime, nullable=False),
    Column("revoked_at", DateTime),
)


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def production_engine() -> Engine:
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSL_CA")
    for name in required:
        if not os.environ.get("DOCUPROCESS_" + name):
            raise RuntimeError("Missing configuration: DOCUPROCESS_" + name)
    env = os.environ
    url = URL.create(
        "mysql+pymysql",
        username=env["DOCUPROCESS_DB_USER"],
        password=env["DOCUPROCESS_DB_PASSWORD"],
        host=env["DOCUPROCESS_DB_HOST"],
        database=env["DOCUPROCESS_DB_NAME"],
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        url,
        pool_size=5,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            "ssl_ca": env["DOCUPROCESS_DB_SSL_CA"],
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        },
    )
