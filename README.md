# GunGong

A LINE bot and Mini App for checking suspicious links, QR codes, and messages. The Mini App also includes community posts, scan history, summary charts, and tip reporting.

Built with React, Vite, FastAPI, Gemini, VirusTotal, and Cloud Firestore. Automated results are indicators, not guarantees of safety.

## Local Development

Requires Python 3.12 and Node.js with npm. Configure the root `.env` using [the environment template](env.example/.env.example). Keep credentials out of version control.

From the repository root, set up and start the backend:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn src.backend.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```powershell
cd src/frontend
npm.cmd ci
npm.cmd run dev
```

Open the localhost URL printed by Vite, normally `http://localhost:5173`. LINE-specific features require the appropriate LINE configuration and environment.

## Project Layout

- `src/frontend/src/features/`: feature-specific UI and logic.
- `src/frontend/src/shared/`: shared components and utilities.
- `src/backend/`: API routes, services, and integrations.
- `tests/` and `src/frontend/tests/`: regression tests.
- `docs/`: feature and deployment documentation.

See [Project Structure](docs/PROJECT_STRUCTURE.md) and [Vercel Deployment](docs/deployment/VERCEL_MIGRATION.md) for details.
