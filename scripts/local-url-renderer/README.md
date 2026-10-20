# Local URL renderer

Optional Chromium worker for local URL-verification tests, not a hosted service.
Rendering is disabled by default. See the [project overview](../../README.md).

## Start

Requires PowerShell 7, Docker Desktop, and an explicitly reviewed,
Chromium-compatible seccomp profile. No generic profile is supplied. From the
repository root, in the **same shell** that will start the local API:

```powershell
& .\scripts\local-url-renderer\start-local.ps1 -SeccompProfile 'C:\absolute\reviewed-profile.json'
$env:URL_RENDER_ENABLED = 'true'
.\.venv\Scripts\python.exe -m uvicorn src.backend.main:app --port 8000
```

The script sets a process-only loopback worker URL and ephemeral authentication
token; it does not change `.env`, stop another API, or enable a hosted worker.
Do not enable rendering without the worker URL: that selects the older in-process
renderer instead. Stop the test container when finished.

## Boundaries

- Keep Chromium's sandbox enabled. Never mount secrets or the Docker socket,
  pass `.env`/provider credentials into Docker, or weaken host policies to start it.
- The worker runs non-root, with a read-only root, dropped capabilities,
  no-new-privileges, private temporary storage, 768 MiB RAM/no swap, one CPU,
  and 128 processes. Its port binds only to `127.0.0.1:8071`.
- The API forwards no user headers or provider credentials. The worker accepts
  bounded URL/HTML inputs, allows one job at a time, and limits work to four
  seconds. Public-network validation and an IP-pinned resource broker restrict
  fetches; forms, WebSockets and service workers are blocked.
- Docker bridge networking and application checks are not production egress
  isolation or browser-exploit protection. Review actual host sandbox, network
  and resource limits before any production use.
- A completed render is not a safe verdict. Worker failure or missing evidence
  remains incomplete unless other trustworthy danger evidence exists. Do not
  log tokens, HTML, or sensitive URL queries.
