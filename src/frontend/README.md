# GunGong frontend

React + Vite Mini App. `src/App.jsx` controls existing routes; `src/main.jsx` is the
entrypoint. Run the frontend locally from `src/frontend`.

- `src/features/`: home, community, scanner, history, report, auth and privacy.
  Keep a feature's UI, styles, hooks and helpers together.
- `src/shared/`: layout, navigation, API transport, cache, result presentation,
  QR camera/image utilities and global styles. Used by more than one feature.
- `public/img/`: images used by the active frontend; tests check references.
- `tests/`: regression tests, including relative-import and QR-worker checks.

See the [repository overview](../../README.md) for setup, features and data boundaries.

## Local development

From this directory:

```powershell
npm.cmd ci
npm.cmd run dev
```

Vite prints the localhost URL (normally `http://localhost:5173`). Start the backend
from the repository root in a second terminal:

```powershell
.venv/Scripts/python.exe -m uvicorn src.backend.main:app --reload --port 8000
```

The Vite environment directory still points to the repository root; no secrets
were moved into frontend source. LINE camera scanning must be verified in LINE;
local image decoding does not upload the image or automatically submit a request.

## Checks

```powershell
npm.cmd test
npm.cmd run build
```

Do not create sample history or write to production Firestore for a layout or
folder check. Use test fixtures / mocked transport instead.
