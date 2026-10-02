# Manual operations

- `data/`: imports, cache maintenance, database migrations and Firestore checks.
  These can read or modify real data. They are not run during build or tests.
- `legacy/cloud-run/`: historical deployment/setup scripts retained for reference.
  The active deployment is Vercel via the root `Dockerfile` and `vercel.json`.

Run scripts from the repository root and review their target configuration first.
This reorganization does not execute any script or modify credentials.
