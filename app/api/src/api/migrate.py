"""Forward-only MySQL migrations guarded by a connection-scoped advisory lock."""

import os
from importlib.resources import files
from sqlalchemy import text
from sqlalchemy.engine import Engine
from .db import now, production_engine


def migrate(engine: Engine) -> None:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        if connection.execute(text("SELECT GET_LOCK('docuprocess_migrations', 60)")).scalar() != 1:
            raise RuntimeError("Migration lock unavailable")
        try:
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(64) PRIMARY KEY, applied_at DATETIME(6) NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )
            )
            migrations = files("api").joinpath("migrations")
            for migration in sorted(migrations.iterdir(), key=lambda p: p.name):
                if not migration.name.endswith(".sql"):
                    continue
                if connection.execute(
                    text("SELECT version FROM schema_migrations WHERE version=:v"),
                    {"v": migration.name},
                ).first():
                    continue
                for statement in migration.read_text().split(";"):
                    if statement.strip():
                        connection.execute(text(statement))
                connection.execute(
                    text("INSERT INTO schema_migrations VALUES (:v,:t)"),
                    {"v": migration.name, "t": now()},
                )
            email = os.environ.get("DOCUPROCESS_BOOTSTRAP_ADMIN_EMAIL")
            if email:
                changed = connection.execute(
                    text("UPDATE users SET role='admin' WHERE email=:email"),
                    {"email": email.strip().lower()},
                )
                if not changed.rowcount:
                    raise RuntimeError("Register the bootstrap user before promoting it")
        finally:
            connection.execute(text("SELECT RELEASE_LOCK('docuprocess_migrations')"))


if __name__ == "__main__":
    engine = production_engine()
    try:
        migrate(engine)
    finally:
        engine.dispose()
