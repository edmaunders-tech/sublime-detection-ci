"""Validate and backtest Sublime detection rules.

Usage:
  python scripts/detection_ci.py                      # all rules in detection-rules/
  python scripts/detection_ci.py detection-rules/a.yml ...   # specific rules (local use)

Local use: put SUBLIME_BASE_URL and SUBLIME_API_TOKEN in a .env file (gitignored).
In CI, message details (subject/sender/mailbox) are NOT written to the run summary.
Set SHOW_MESSAGE_DETAILS=1 to include them (default: on locally, off in GitHub Actions).
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml


def load_dotenv(path=".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


load_dotenv()

BASE_URL = os.environ["SUBLIME_BASE_URL"].rstrip("/")
TOKEN = os.environ["SUBLIME_API_TOKEN"]

LOOKBACK_DAYS = int(os.environ.get("HUNT_LOOKBACK_DAYS", "14"))
MIN_MATCHES = int(os.environ.get("MIN_MATCHES", "1"))
MAX_MATCHES = int(os.environ.get("MAX_MATCHES", "50"))
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"
SHOW_DETAILS = os.environ.get("SHOW_MESSAGE_DETAILS", "0" if IN_CI else "1") == "1"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}


def get_rules(args):
    if args:
        return [Path(a) for a in args]
    return sorted(
        list(Path("detection-rules").rglob("*.yml"))
        + list(Path("detection-rules").rglob("*.yaml"))
    )


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
    # Ask for one more than MAX_MATCHES so we can tell "at the limit" from "over it".
    r = requests.get(
        f"{BASE_URL}/v0/hunt-jobs/{hunt_id}/results",
        headers=HEADERS,
        params={"limit": MAX_MATCHES + 1, "offset": 0},
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
        if isinstance(value, dict):  # e.g. sender: {"email": {...}}
            value = value.get("email") or value.get("address") or value.get("name")
        if value:
            return str(value)
    return "unknown"


def md_escape(text, limit=60):
    """Make untrusted text safe for a markdown table cell."""
    text = " ".join(str(text).split())
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    for ch in "|`<>[]":
        text = text.replace(ch, "\\" + ch)
    return text


def message_fields(result):
    return (
        pick_field(result, ["subject", "message_subject", "summary", "name"]),
        pick_field(result, ["sender", "from", "from_address", "sender_address"]),
        pick_field(result, ["mailbox", "mailbox_email_address", "recipient", "recipient_address"]),
        pick_field(result, ["id", "message_group_id", "canonical_id"]),
    )


def write_summary(rule_name, match_count, results, hard_fail=False, fail_reason=None):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    rule_name = md_escape(rule_name, 120)
    with open(summary_path, "a") as f:
        if hard_fail:
            f.write(f"## ❌ {rule_name}\n")
            f.write(f"**Hard failure:** {md_escape(fail_reason, 500)}\n\n")
            return

        over = match_count > MAX_MATCHES
        shown = f"{MAX_MATCHES}+" if over else str(match_count)

        warnings = []
        if match_count < MIN_MATCHES:
            warnings.append(f"⚠️ Low match count — only {match_count} matched (min threshold: {MIN_MATCHES}). Possible missed detections.")
        if over:
            warnings.append(f"⚠️ High match count — more than {MAX_MATCHES} matched. Possible noise/FPs.")

        f.write(f"## 🔍 {rule_name}\n")
        f.write(f"**Matches found:** {shown} | **Lookback:** {LOOKBACK_DAYS} days | **Threshold:** {MIN_MATCHES}–{MAX_MATCHES}\n\n")

        if warnings:
            for w in warnings:
                f.write(f"> {w}\n")
            f.write("\n")
        else:
            f.write("> ✅ Match count within expected threshold.\n\n")

        if results and SHOW_DETAILS:
            f.write("### Matched Messages — please review for false positives before approving\n\n")
            f.write("| # | Subject | Sender | Mailbox | Group ID |\n")
            f.write("|---|---------|--------|---------|----------|\n")
            for i, result in enumerate(results[:MAX_MATCHES], start=1):
                subject, sender, mailbox, group_id = (md_escape(v) for v in message_fields(result))
                f.write(f"| {i} | {subject} | {sender} | {mailbox} | {group_id} |\n")
            f.write("\n")
        elif results:
            f.write("### Matched message group IDs — open these in Sublime to review for false positives\n\n")
            for result in results[:MAX_MATCHES]:
                f.write(f"- `{md_escape(message_fields(result)[3], 80)}`\n")
            f.write("\n")
        else:
            f.write("> ℹ️ No messages matched.\n\n")

        f.write("---\n")
        f.write("👆 **Admin: review the matches above then approve or reject the `review` environment in the next job.**\n")


def test_rule(path):
    """Returns True if the rule passed validation and the hunt ran. Matches never fail."""
    print(f"\n--- Testing {path} ---")

    with open(path, "r", encoding="utf-8") as f:
        rule = yaml.safe_load(f)
    name = rule.get("name", str(path)) if isinstance(rule, dict) else str(path)

    if not isinstance(rule, dict) or "source" not in rule:
        print("❌ Not a valid rule file (missing source)")
        write_summary(name, 0, [], hard_fail=True, fail_reason="Not a valid rule file (missing source)")
        return False

    ok, validation_response = validate(rule)
    if not ok:
        print("❌ Rule validation failed")
        print(validation_response)
        write_summary(name, 0, [], hard_fail=True, fail_reason=f"Validation failed: {validation_response}")
        return False
    print("✅ Rule validation passed")

    hunt_id = start_hunt(rule)
    print(f"🚀 Hunt started: {hunt_id}")

    hunt = wait_for_hunt(hunt_id)
    if hunt.get("status") != "COMPLETED":
        print("❌ Hunt did not complete successfully")
        write_summary(name, 0, [], hard_fail=True, fail_reason=f"Hunt status: {hunt.get('status')}")
        return False
    print("✅ Hunt completed")

    if hunt.get("results_truncated"):
        print("❌ Results truncated — rule may be too broad")
        write_summary(name, 0, [], hard_fail=True, fail_reason="Results truncated — detection is too broad.")
        return False

    results = get_hunt_results(hunt_id)
    match_count = len(results)
    over = match_count > MAX_MATCHES

    print(f"\n📊 Matched messages: {MAX_MATCHES}+" if over else f"\n📊 Matched messages: {match_count}")
    print(f"Threshold: {MIN_MATCHES} to {MAX_MATCHES}")

    if results and SHOW_DETAILS:
        print("\nMatched message examples:")
        for i, result in enumerate(results[:10], start=1):
            subject, sender, mailbox, group_id = message_fields(result)
            print(f"{i}. Subject: {subject}")
            print(f"   Sender:  {sender}")
            print(f"   Mailbox: {mailbox}")
            print(f"   Group:   {group_id}")

    write_summary(name, match_count, results)
    return True


def main():
    rules = get_rules(sys.argv[1:])

    if not rules:
        print("No rules found")
        return

    failed = []
    for path in rules:
        try:
            if not test_rule(path):
                failed.append(str(path))
        except Exception as e:  # keep going so one bad rule doesn't hide the rest
            print(f"❌ Error testing {path}: {e}")
            write_summary(str(path), 0, [], hard_fail=True, fail_reason=str(e))
            failed.append(str(path))

    if failed:
        print(f"\n❌ {len(failed)} rule(s) failed: {', '.join(failed)}")
        sys.exit(1)

    print("\n⏸️  Waiting for admin approval in the next job...")


if __name__ == "__main__":
    main()
