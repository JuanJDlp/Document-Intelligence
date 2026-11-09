"""Install the release in an isolated environment; never use live AWS credentials."""

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(version: str) -> None:
    archive_path = ROOT / "dist" / ("docuprocess-" + version + ".tar.gz")
    with tempfile.TemporaryDirectory(prefix="docuprocess-package-") as folder:
        target = Path(folder)
        with tarfile.open(archive_path) as archive:
            assert all(
                not member.name.startswith("/") and ".." not in Path(member.name).parts
                for member in archive.getmembers()
            )
            archive.extractall(target, filter="data")
        assert (target / "packages/api/src/api/migrations/0001_init.sql").is_file()
        subprocess.run(["uv", "venv", "--python", sys.executable, str(target / "venv")], check=True)
        python = target / "venv/bin/python"
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "-r",
                str(target / "requirements.lock"),
            ],
            check=True,
        )
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-deps",
                *[str(target / "packages" / name) for name in ("receipt_engine", "api", "worker")],
            ],
            check=True,
        )
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AWS_", "DOCUPROCESS_"))}
        env["AWS_EC2_METADATA_DISABLED"] = "true"
        subprocess.run(
            [
                str(python),
                "-c",
                "from receipt_engine import ReceiptExtractionEngine; from api.main import app; from worker.main import Worker; from importlib.resources import files; assert files('api').joinpath('migrations/0001_init.sql').is_file(); assert '/api/v1/health' in app.openapi()['paths']",
            ],
            cwd=folder,
            env=env,
            check=True,
        )
    print("package-check: isolated install and imports OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0.0")
    verify(parser.parse_args().version)
