import os
import time
import requests
import yaml
from pathlib import Path

BASE_URL = os.environ["SUBLIME_BASE_URL"].rstrip("/")
TOKEN = os.environ["SUBLIME_API_TOKEN"]
EXPECTED_MATCH_COUNT = int(os.environ.get("EXPECTED_MATCH_COUNT", "2"))

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

def get_rules():
    return list(Path("detection-rules").rglob("*.yml"))

def validate(rule):
    r = requests.post(f"{BASE_URL}/v0/rules/validate", headers=HEADERS, json=rule)
    return r.ok, r.text

def start_hunt(rule):
    payload = {
        "name": f"CI Backtest: {rule['name']}",
        "source": rule["source"],
    }

    r = requests.post(f"{BASE_URL}/v0/hunt-jobs", headers=HEADERS, json=payload)

    if not r.ok:
        raise Exception(r.text)

    return r.json()["hunt_job_id"]

def get_hunt(hunt_id):
    r = requests.get(f"{BASE_URL}/v0/hunt-jobs/{hunt_id}", headers=HEADERS)

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

def extract_match_count(hunt):
    # This depends slightly on the API response shape.
    # These cover the common likely field names.
    for key in ["match_count", "matches_count", "result_count", "results_count", "total_results"]:
        if key in hunt:
            return int(hunt[key])

    if "results" in hunt and isinstance(hunt["results"], list):
        return len(hunt["results"])

    print("Could not find match count in Hunt response:")
    print(hunt)
    raise Exception("Unable to determine Hunt match count")

def main():
    rules = get_rules()

    if not rules:
        print("No rules found")
        return

    for path in rules:
        print(f"\n--- Testing {path} ---")

        rule = yaml.safe_load(open(path))

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

        match_count = extract_match_count(hunt)

        print(f"📊 Hunt matched {match_count} emails")

        if match_count != EXPECTED_MATCH_COUNT:
            print(f"❌ Backtest failed. Expected {EXPECTED_MATCH_COUNT}, got {match_count}")
            exit(1)

        print("✅ Backtest passed. Detection only matched the expected bad emails.")

if __name__ == "__main__":
    main()