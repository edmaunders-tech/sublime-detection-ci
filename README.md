# Sublime detection CI (demo)

Write a rule in `detection-rules/`, backtest it locally, open a PR, approve, merge. Sublime pulls `main` as a feed, so merging deploys.

## Local backtest
    pip install requests pyyaml
    printf 'SUBLIME_BASE_URL=https://...\nSUBLIME_API_TOKEN=...\n' > .env   # gitignored
    python scripts/detection_ci.py detection-rules/my_rule.yml

Prints validation, hunt status and matched messages (subject/sender/mailbox) in your terminal.

## In CI
PRs touching `detection-rules/` run validate + a 14-day hunt, write a summary, then wait for approval of the `review` environment. In CI the summary shows counts and group IDs only, not message details.

Demo caveats: the CI job runs PR code with the API token, so don't use this setup as-is for untrusted contributors. Protect `main` and require the `admin-review` check.
