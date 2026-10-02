# GunGong frontend

React + Vite Mini App. `src/App.jsx` controls existing routes; `src/main.jsx` is the
entrypoint. Vercel's frontend root remains `src/frontend`.

- `src/features/`: home, community, scanner, history, report, auth and privacy.
  Keep a feature's UI, styles, hooks and helpers together.
- `src/shared/`: layout, navigation, API transport, cache, result presentation,
  QR camera/image utilities and global styles. Used by more than one feature.
- `src/legacy/verify/`: inactive Verify / ID-card UI kept in source.
- `public/img/`: stable image URLs; do not rename without updating callers.
- `tests/`: regression tests, including relative-import and QR-worker checks.

Full [repository and backend feature map](../../docs/PROJECT_STRUCTURE.md).

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
