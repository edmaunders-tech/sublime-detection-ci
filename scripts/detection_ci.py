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


def write_summary(rule_name, match_count, results, hard_fail=False, fail_reason=None):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    with open(summary_path, "a") as f:

        if hard_fail:
            f.write(f"## ❌ {rule_name}\n")
            f.write(f"**Hard failure:** {fail_reason}\n\n")
            return

        # Informational warnings for admin to consider
        warnings = []
        if match_count < MIN_MATCHES:
            warnings.append(f"⚠️ Low match count — only {match_count} matched (min threshold: {MIN_MATCHES}). Possible missed detections.")
        if match_count > MAX_MATCHES:
            warnings.append(f"⚠️ High match count — {match_count} matched (max threshold: {MAX_MATCHES}). Possible noise/FPs.")

        f.write(f"## 🔍 {rule_name}\n")
        f.write(f"**Matches found:** {match_count} | **Lookback:** {LOOKBACK_DAYS} days | **Threshold:** {MIN_MATCHES}–{MAX_MATCHES}\n\n")

        if warnings:
            for w in warnings:
                f.write(f"> {w}\n")
            f.write("\n")
        else:
            f.write("> ✅ Match count within expected threshold.\n\n")

        if results:
            f.write("### Matched Messages — please review for false positives before approving\n\n")
            f.write("| # | Subject | Sender | Mailbox | Group ID |\n")
            f.write("|---|---------|--------|---------|----------|\n")

            for i, result in enumerate(results[:50], start=1):
                subject = pick_field(result, ["subject", "message_subject", "summary", "name"])
                sender = pick_field(result, ["sender", "from", "from_address", "sender_address"])
                mailbox = pick_field(result, ["mailbox", "mailbox_email_address", "recipient", "recipient_address"])
                group_id = pick_field(result, ["id", "message_group_id", "canonical_id"])

                # truncate long subjects
                if len(subject) > 60:
                    subject = subject[:57] + "..."

                f.write(f"| {i} | {subject} | {sender} | {mailbox} | {group_id} |\n")

            f.write("\n")
        else:
            f.write("> ℹ️ No messages matched.\n\n")

        f.write("---\n")
        f.write("👆 **Admin: review the matches above then approve or reject the `review` environment in the next job.**\n")


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
            write_summary(rule.get("name", str(path)), 0, [], hard_fail=True, fail_reason=f"Validation failed: {validation_response}")
            exit(1)

        print("✅ Rule validation passed")

        hunt_id = start_hunt(rule)
        print(f"🚀 Hunt started: {hunt_id}")

        hunt = wait_for_hunt(hunt_id)

        if hunt.get("status") != "COMPLETED":
            print("❌ Hunt did not complete successfully")
            write_summary(rule.get("name", str(path)), 0, [], hard_fail=True, fail_reason=f"Hunt status: {hunt.get('status')}")
            exit(1)

        print("✅ Hunt completed")

        if hunt.get("results_truncated"):
            print("❌ Results truncated — rule may be too broad")
            write_summary(rule.get("name", str(path)), 0, [], hard_fail=True, fail_reason="Results truncated — detection is too broad.")
            exit(1)

        results = get_hunt_results(hunt_id)
        match_count = len(results)

        print(f"\n📊 Matched messages: {match_count}")
        print(f"Threshold: {MIN_MATCHES} to {MAX_MATCHES}")

        # Print to log as before
        if results:
            print("\nMatched message examples:")
            for i, result in enumerate(results[:10], start=1):
                subject = pick_field(result, ["subject", "message_subject", "summary", "name"])
                sender = pick_field(result, ["sender", "from", "from_address", "sender_address"])
                mailbox = pick_field(result, ["mailbox", "mailbox_email_address", "recipient", "recipient_address"])
                group_id = pick_field(result, ["id", "message_group_id", "canonical_id"])
                print(f"{i}. Subject: {subject}")
                print(f"   Sender:  {sender}")
                print(f"   Mailbox: {mailbox}")
                print(f"   Group:   {group_id}")

        # Write summary for admin review — no hard fail on count anymore
        write_summary(rule["name"], match_count, results)

        print("\n⏸️  Waiting for admin approval in the next job...")


if __name__ == "__main__":
    main()