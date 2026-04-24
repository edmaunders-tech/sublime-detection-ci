import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

BASE_URL = os.environ["SUBLIME_BASE_URL"].rstrip("/")
TOKEN = os.environ["SUBLIME_API_TOKEN"]

LOOKBACK_DAYS = int(os.environ.get("HUNT_LOOKBACK_DAYS", "14"))
MIN_MATCHES = int(os.environ.get("MIN_MATCHES", "1"))
MAX_MATCHES = int(os.environ.get("MAX_MATCHES", "50"))

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


def get_hunt_results(hunt_id):
    r = requests.get(
        f"{BASE_URL}/v0/hunt-jobs/{hunt_id}/results",
        headers=HEADERS,
        params={"limit": 50, "offset": 0},
        timeout=60,
    )

    if not r.ok:
        raise Exception(r.text)

    body = r.json()

    if isinstance(body, list):
        return body

    for key in ["results", "data", "items", "message_groups"]:
        if key in body and isinstance(body[key], list):
            return body[key]

    print("Could not find results list in response:")
    print(body)
    return []


def pick_field(obj, possible_keys):
    for key in possible_keys:
        value = obj.get(key)
        if value:
            return value
    return "unknown"


def print_result_examples(results):
    print("\nMatched message examples:")

    for index, result in enumerate(results[:10], start=1):
        subject = pick_field(
            result,
            ["subject", "message_subject", "summary", "name"],
        )

        sender = pick_field(
            result,
            ["sender", "from", "from_address", "sender_address"],
        )

        mailbox = pick_field(
            result,
            ["mailbox", "mailbox_email_address", "recipient", "recipient_address"],
        )

        group_id = pick_field(
            result,
            ["id", "message_group_id", "canonical_id"],
        )

        print(f"{index}. Subject: {subject}")
        print(f"   Sender:  {sender}")
        print(f"   Mailbox: {mailbox}")
        print(f"   Group:   {group_id}")


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
            print("❌ Backtest failed. Results were truncated, detection may be too broad.")
            exit(1)

        results = get_hunt_results(hunt_id)
        match_count = len(results)

        print(f"\n📊 Matched messages: {match_count}")
        print(f"Threshold: {MIN_MATCHES} to {MAX_MATCHES}")

        if results:
            print_result_examples(results)

        if match_count < MIN_MATCHES:
            print("❌ Backtest failed. Detection did not match enough messages.")
            exit(1)

        if match_count > MAX_MATCHES:
            print("❌ Backtest failed. Detection matched too many messages and may be noisy.")
            exit(1)

        print("✅ Backtest passed. Detection matched within the allowed threshold.")


if __name__ == "__main__":
    main()