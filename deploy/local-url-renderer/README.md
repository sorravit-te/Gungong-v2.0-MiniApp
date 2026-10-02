# Local URL renderer worker

This directory used to be `deploy/renderer/`. It is **not** a Render.com service.
It contains an optional, isolated Chromium worker for collecting evidence from
JavaScript-driven URLs during local testing.

- Active Vercel deployment: root `Dockerfile` and `vercel.json`, unchanged.
- Worker package: `src.backend.services.renderer_worker_app`, unchanged.
- Worker startup and reviewed isolation requirements:
  [local worker guide](../../docs/deployment/url-renderer/LOCAL_RENDERER_WORKER.md).
- `start-local.ps1` still resolves the repository root two directories upward.

Do not run this worker or configure its credentials automatically. Do not delete
the URL-rendering services merely because Render hosting is no longer used.
