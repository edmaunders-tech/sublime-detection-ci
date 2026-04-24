import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

BASE_URL = os.environ["SUBLIME_BASE_URL"].rstrip("/")
TOKEN = os.environ["SUBLIME_API_TOKEN"]
LOOKBACK_DAYS = int(os.environ.get("HUNT_LOOKBACK_DAYS", "14"))

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


def get_rules():
    return list(Path("detection-rules").rglob("*.yml"))


def validate(rule):
    r = requests.post(
        f"{BASE_URL}/v0/rules/validate",
        headers=HEADERS,
        json=rule,
        timeout=60,
    )
    return r.ok, r.text


def start_hunt(rule):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=LOOKBACK_DAYS)

    payload = {
        "name": f"CI Backtest: {rule['name']}",
        "private": True,
        "source": rule["source"],
        "range_start_time": start.isoformat().replace("+00:00", "Z"),
        "range_end_time": now.isoformat().replace("+00:00", "Z"),
    }

    r = requests.post(
        f"{BASE_URL}/v0/hunt-jobs",
        headers=HEADERS,
        json=payload,
        timeout=60,
    )

    if not r.ok:
        raise Exception(r.text)

    body = r.json()
    return body.get("hunt_job_id") or body.get("id")


def get_hunt(hunt_id):
    r = requests.get(
        f"{BASE_URL}/v0/hunt-jobs/{hunt_id}",
        headers=HEADERS,
        timeout=60,
    )

    if not r.ok:
        raise Exception(r.text)

    return r.json()


def wait_for_hunt(hunt_id):
    for _ in range(40):
        hunt = get_hunt(hunt_id)
        status = hunt.get("status")

        print(f"Hunt status: {status}")

        if status in ["COMPLETED", "FAILED", "CANCELED"]:
            return hunt

        time.sleep(15)

    raise Exception("Hunt timed out")


def main():
    rules = get_rules()

    if not rules:
        print("No rules found")
        return

    for path in rules:
        print(f"\n--- Testing {path} ---")

        with open(path, "r", encoding="utf-8") as f:
            rule = yaml.safe_load(f)

        ok, validation_response = validate(rule)

        if not ok:
            print("❌ Rule validation failed")
            print(validation_response)
            exit(1)

        print("✅ Rule validation passed")

        hunt_id = start_hunt(rule)
        print(f"🚀 Hunt started: {hunt_id}")

        hunt = wait_for_hunt(hunt_id)

        if hunt.get("status") != "COMPLETED":
            print("❌ Hunt did not complete successfully")
            print(hunt)
            exit(1)

        print("📊 Hunt completed successfully")
        print(f"Results truncated: {hunt.get('results_truncated')}")

        if hunt.get("results_truncated"):
            print("❌ Backtest failed. Hunt results were truncated, detection may be too broad.")
            exit(1)

        # Demo gate:
        # The hunt status endpoint does not return match count.
        # For this demo failure branch, we intentionally fail after a clean hunt
        # to show how CI would block a detection that does not meet expected results.
        print("⚠️ Demo gate: no match-count field returned by Hunt status endpoint.")
        print("❌ Backtest failed. Detection did not meet expected match criteria.")
        exit(1)


if __name__ == "__main__":
    main()