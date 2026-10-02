# Project structure

The frontend is feature-first. Backend Python package names, API routes, public
asset URLs, environment keys, and Vercel service roots are deliberately unchanged.
This is a relocation, not a redesign or a deployment.

```text
src/
  frontend/
    src/
      App.jsx / main.jsx          Application routing and entrypoint
      features/
        home/                     Banner and Summary charts
        community/                Feed, posts, comments, images and likes
        scanner/                  Link/QR and message checks
        history/                  Calendar, filters, entries and detail reader
        report/                   Tip submission form and client
        auth/                     LINE session, login and Firebase initialization
        privacy/                  PDPA notice
      shared/
        layout/                   Sidebar, bottom navigation and top banner
        navigation/               Main menu definitions
        api/                      Existing API transport and response parser
        cache/                    Shared in-memory page cache
        results/                  Common result presentation
        qr/                       Camera/image QR reader and its worker
        styles/                   Global styles
      legacy/verify/              Preserved, inactive Verify and ID-card UI
    public/img/                   Stable public image paths (not renamed)
    tests/                        Frontend regression tests and fixtures
  backend/
    main.py                       Existing FastAPI entrypoint
    routers/                      Feature-specific HTTP endpoints
    services/                     Backend business logic and integrations
    core/                         Settings, models and AI prompt/pattern data
    utils/                        Flex templates and message helpers
docs/
  features/                       Current feature contracts
  deployment/                     Vercel and URL-renderer operations
  legacy/verify/                  Preserved Verify documentation
deploy/local-url-renderer/        Optional local Chromium worker, not Render hosting
scripts/
  data/                           Manual database maintenance/import commands
  legacy/cloud-run/               Old Cloud Run scripts, not the active deployment
tests/                            Backend regression tests
```

## Where to change each feature

| Feature | Frontend | Existing backend entrypoints |
| --- | --- | --- |
| Home / Summary | `features/home/` | History API data |
| Community | `features/community/` | `routers/community.py`, `services/community_image_service.py` |
| Link / QR scan | `features/scanner/`, `shared/qr/` | `routers/fraud.py`, `services/url_*`, `services/virustotal_service.py` |
| Message scan | `features/scanner/` | `routers/fraud.py`, `routers/fraud_v2.py`, message/AI services |
| History | `features/history/` | `routers/history.py`, `services/database_service.py` |
| Report | `features/report/` | `routers/reports.py` |
| LINE bot | LINE integration in `features/auth/` | `routers/webhook.py`, `services/line_service.py`, `utils/flex_templates.py` |
| Verify (inactive UI) | `legacy/verify/` | Existing verification modules retained; backend routes were not disabled by this move |

Do not put feature-only components in `shared/`. Import shared modules directly;
avoid a catch-all barrel file. Keep actual API, authentication, cancellation and
result contracts unchanged when moving files.

## Renderer is not Render

`renderer` means rendering JavaScript-driven pages with Chromium for URL evidence.
It does **not** mean the hosting provider Render. The old `deploy/renderer/` path
is now `deploy/local-url-renderer/`; the worker implementation remains in
`src/backend/services/`. It is optional, local-only, and controlled by existing
`URL_RENDER_*` settings. The configuration defaults to rendering disabled.

Vercel still uses the root `Dockerfile` and `vercel.json`. It does not reference
the local-worker Dockerfile or the historical Cloud Run scripts. Nothing here
changes an external Render account, Git integration, LINE webhook, or LIFF endpoint.

See [worker instructions](deployment/url-renderer/LOCAL_RENDERER_WORKER.md) and
[Vercel deployment](deployment/VERCEL_MIGRATION.md).

## Local verification

Run frontend commands from `src/frontend/`:

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run dev
```

Run backend commands from the repository root:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py'
.venv/Scripts/python.exe -m uvicorn src.backend.main:app --reload --port 8000
```

Chromium isolation tests require a working sandbox; do not bypass it to make a
test pass. Database scripts are manual operations, not smoke tests: do not run
them against production during a folder reorganization.
