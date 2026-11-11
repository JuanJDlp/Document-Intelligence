"""Traffic simulation to demonstrate Auto Scaling (TST-MK-16, TST-E2E-11).

Registers one synthetic user, then runs concurrent login/logout pairs against the
public CloudFront URL. Each login verifies an Argon2id hash, so the traffic is
CPU-bound on the instances and drives the ASG target-tracking policy (CPU 60 %).
Every 30 s it prints request counts, ASG capacity and ASG average CPU.
Prints no tokens, passwords or response bodies.
"""

import os
import secrets
import threading
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import boto3
import httpx

REPORT_SECONDS = 30


def env_int(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if value < 1:
        raise RuntimeError(f"{name} must be positive")
    return value


def register(base: str) -> dict[str, str]:
    identity = {
        "email": f"load+{uuid4()}@example.com",
        "password": secrets.token_urlsafe(24) + "1",
        "full_name": "Synthetic Load User",
    }
    response = httpx.post(base + "/auth/register", json=identity, timeout=30)
    if response.status_code != 201:
        raise RuntimeError(f"register failed: HTTP {response.status_code}")
    return {"email": identity["email"], "password": identity["password"]}


def worker(
    base: str,
    credentials: dict[str, str],
    stop: threading.Event,
    stats: Counter[str],
    lock: threading.Lock,
) -> None:
    with httpx.Client(base_url=base, timeout=30) as client:
        while not stop.is_set():
            try:
                login = client.post("/auth/login", json=credentials)
                status = str(login.status_code)
                if login.status_code == 200:
                    token = login.json()["token"]
                    client.post("/auth/logout", headers={"Authorization": "Bearer " + token})
            except httpx.HTTPError as exc:
                status = type(exc).__name__
            with lock:
                stats[status] += 1


def asg_snapshot(asg_name: str) -> str:
    autoscaling = boto3.client("autoscaling")
    cloudwatch = boto3.client("cloudwatch")
    group = autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])[
        "AutoScalingGroups"
    ][0]
    in_service = sum(1 for i in group["Instances"] if i["LifecycleState"] == "InService")
    now = datetime.now(UTC)
    points = cloudwatch.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName="CPUUtilization",
        Dimensions=[{"Name": "AutoScalingGroupName", "Value": asg_name}],
        StartTime=now - timedelta(minutes=15),
        EndTime=now,
        Period=60,
        Statistics=["Average"],
    )["Datapoints"]
    cpu = "n/a"
    if points:
        latest = max(points, key=lambda p: p["Timestamp"])
        cpu = f"{latest['Average']:.0f}% at {latest['Timestamp']:%H:%M}Z"
    return f"asg desired={group['DesiredCapacity']} in_service={in_service} max={group['MaxSize']} cpu={cpu}"


def run() -> None:
    base = os.environ.get("LOAD_BASE_URL", "").rstrip("/")
    if not base.startswith("https://"):
        raise RuntimeError("Set LOAD_BASE_URL to the CloudFront HTTPS URL")
    base += "/api/v1"
    asg_name = os.environ.get("LOAD_ASG_NAME", "")
    if not asg_name:
        raise RuntimeError("Set LOAD_ASG_NAME to the Auto Scaling group name")
    minutes = env_int("LOAD_MINUTES", 10)
    workers = env_int("LOAD_WORKERS", 24)

    credentials = register(base)
    stop = threading.Event()
    stats: Counter[str] = Counter()
    lock = threading.Lock()
    threads = [
        threading.Thread(target=worker, args=(base, credentials, stop, stats, lock), daemon=True)
        for _ in range(workers)
    ]
    print(f"load: {workers} workers for {minutes} min against {base}")
    print(asg_snapshot(asg_name))
    for thread in threads:
        thread.start()

    started = time.monotonic()
    deadline = started + minutes * 60
    previous = 0
    try:
        while time.monotonic() < deadline:
            time.sleep(min(REPORT_SECONDS, max(0.0, deadline - time.monotonic())))
            with lock:
                total = sum(stats.values())
                summary = " ".join(f"{k}={v}" for k, v in sorted(stats.items()))
            rate = (total - previous) / REPORT_SECONDS
            previous = total
            elapsed = int(time.monotonic() - started)
            print(
                f"t+{elapsed:4d}s logins={total} ({rate:.1f}/s) [{summary}] | {asg_snapshot(asg_name)}"
            )
    except KeyboardInterrupt:
        print("load: interrupted")
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=35)
    print("load: stopped. The ASG scales in again after the cooldown (about 15 min).")
    print(asg_snapshot(asg_name))


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001 - top-level guard prints only the class name
        print(
            "Load test failed:",
            type(exc).__name__,
            str(exc) if isinstance(exc, RuntimeError) else "",
        )
        raise SystemExit(1) from None
