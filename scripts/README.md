# Manual operations

- `data/`: imports, cache maintenance, database migrations and Firestore checks.
  These can read or modify real data. They are not run during build or tests.
- `local-url-renderer/`: optional isolated Chromium worker for local testing only.
  This is not cloud hosting; its isolation and credential exclusions must remain.

Run scripts from the repository root and review their target configuration first.
Cloud deployment/setup scripts are not included. No script is executed automatically.
