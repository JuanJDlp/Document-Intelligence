"""Package only release inputs; never include state, credentials or test documents."""

import argparse
import json
import re
import subprocess
import tarfile
from pathlib import Path
from api.main import app

ROOT = Path(__file__).resolve().parents[1]


def package(version):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", version):
        raise ValueError("Invalid release version")
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    lock = output / "requirements.lock"
    subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-dev",
            "--no-emit-workspace",
            "--no-hashes",
            "--output-file",
            str(lock),
        ],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    (ROOT / "docs/openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")
    target = output / f"docuprocess-{version}.tar.gz"
    with tarfile.open(target, "w:gz") as archive:
        archive.add(lock, arcname="requirements.lock")
        for name in ("receipt_engine", "api", "worker"):
            folder = ROOT / "app" / name
            archive.add(folder / "pyproject.toml", arcname=f"packages/{name}/pyproject.toml")
            for file in (folder / "src").rglob("*"):
                if (
                    file.is_file()
                    and "__pycache__" not in file.parts
                    and not file.name.endswith(".pyc")
                ):
                    archive.add(
                        file, arcname=f"packages/{name}/src/{file.relative_to(folder / 'src')}"
                    )
    print(f"Release packaged: {target.name}")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0.0")
    package(parser.parse_args().version)
