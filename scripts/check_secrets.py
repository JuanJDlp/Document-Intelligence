"""SEC-ACC-01: scan only tracked and nonignored project files; report paths, not values."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        rb"(?im)^\s*(?:aws_secret_access_key|aws_session_token)\s*=\s*(?!<|\$)[A-Za-z0-9/+=]{30,}"
    ),
]


def main() -> int:
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    failures = []
    for name in names:
        path = ROOT / name
        if (
            not name
            or not path.is_file()
            or path.suffix.lower() in {".pdf", ".png", ".jpeg", ".jpg"}
        ):
            continue
        content = path.read_bytes()
        if any(pattern.search(content) for pattern in PATTERNS):
            failures.append(name)
    for name in failures:
        print("Possible secret in:", name)
    if not failures:
        print("check_secrets: OK")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
