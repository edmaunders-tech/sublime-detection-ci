import os
import requests
import yaml
from pathlib import Path

BASE_URL = os.environ["SUBLIME_BASE_URL"].rstrip("/")
TOKEN = os.environ["SUBLIME_API_TOKEN"]

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
    )
    return r.ok, r.text

def start_hunt(rule):
    payload = {
        "name": f"CI Demo: {rule['name']}",
        "source": rule["source"],
    }

    r = requests.post(
        f"{BASE_URL}/v0/hunt-jobs",
        headers=HEADERS,
        json=payload,
    )

    if not r.ok:
        raise Exception(r.text)

    return r.json()["hunt_job_id"]

def main():
    rules = get_rules()

    if not rules:
        print("No rules found")
        return

    for path in rules:
        print(f"\n--- {path} ---")

        rule = yaml.safe_load(open(path))

        ok, res = validate(rule)

        if not ok:
            print("❌ Validation failed")
            print(res)
            exit(1)

        print("✅ Validation passed")

        hunt_id = start_hunt(rule)
        print(f"🚀 Hunt started: {hunt_id}")

if __name__ == "__main__":
    main()