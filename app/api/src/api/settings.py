"""Validated process configuration; never include values in configuration errors."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiSettings:
    region: str
    bucket: str
    documents_table: str
    jobs_table: str
    cors_origin: str | None
    max_upload_bytes: int

    @classmethod
    def from_environment(cls, *, require_aws: bool = True) -> "ApiSettings":
        names = ("AWS_REGION", "UPLOADS_BUCKET", "DOCUMENTS_TABLE", "JOBS_TABLE")
        if require_aws:
            for name in names:
                if not os.environ.get("DOCUPROCESS_" + name):
                    raise RuntimeError("Missing configuration: DOCUPROCESS_" + name)
        try:
            limit = int(os.environ.get("DOCUPROCESS_MAX_UPLOAD_BYTES", "5242880"))
        except ValueError:
            raise RuntimeError("Invalid configuration: DOCUPROCESS_MAX_UPLOAD_BYTES") from None
        if not 1 <= limit <= 5242880:
            raise RuntimeError("Invalid configuration: DOCUPROCESS_MAX_UPLOAD_BYTES")
        return cls(
            os.environ.get("DOCUPROCESS_AWS_REGION", "us-east-1"),
            os.environ.get("DOCUPROCESS_UPLOADS_BUCKET", ""),
            os.environ.get("DOCUPROCESS_DOCUMENTS_TABLE", ""),
            os.environ.get("DOCUPROCESS_JOBS_TABLE", ""),
            os.environ.get("DOCUPROCESS_CORS_ORIGIN") or None,
            limit,
        )
