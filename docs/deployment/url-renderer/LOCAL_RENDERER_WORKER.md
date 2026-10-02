# Local isolated renderer prototype

This is **local testing only**, not a production deployment or a fix for every
HTTP 403/503. The existing 9-second verifier and 12-second frontend limits remain.
No paid service, external rendering provider, database migration or LINE change
is part of this work.

## Boundary

- Build `deploy/local-url-renderer/Dockerfile`, independently of the main API image. Its
  copy allowlist excludes the API application, database/provider services,
  frontend, `.env` and credentials. No Google/Firestore/Gemini SDK is installed.
- `renderer_worker_app` refuses provider/Firestore credential environment
  variables and secret files. It accepts only URL, previously fetched bounded
  HTML, CSP and a maximum four-second work allowance. It cannot accept API keys
  or arbitrary browser options in the request.
- Run non-root, Chromium sandbox **enabled**, all host capabilities dropped,
  no-new-privileges, read-only root, private tmpfs/shared memory, one CPU,
  768 MiB RAM/no swap and 128 processes. Never mount a Docker socket or secrets.
- A dedicated ephemeral token authenticates the worker, not a user/provider key.
  Chromium receives a minimal OS environment that excludes even this worker token.
  Bind its port to `127.0.0.1:8071` only. The API adapter accepts only numeric
  loopback HTTP endpoints with explicit non-privileged ports, does not follow
  worker redirects, uses no environment proxy and forwards no user headers.
- Public DNS validation precedes browser launch. The existing IP-pinned broker
  rechecks resources and retains hostname TLS verification. A deny-all browser
  proxy, blocked service workers/WebSockets, no POST/form submissions and bounded
  resources remain in place. There is no CAPTCHA/anti-bot bypass.
- One render job at a time; excess jobs report unavailable, not an unbounded
  queue. Request/response bytes, body-read time, work time and teardown are bounded.
  Caller disconnect cancels and awaits owned work/browser teardown. Access logs
  are disabled; diagnostics do not print tokens, HTML or sensitive URL queries.

The browser is isolated from API credentials, but this is not a browser-exploit
security certification. Docker bridge egress plus the pinned broker is not a
replacement for a production network policy. Keep production rendering disabled
until the actual host's sandbox, egress and resource boundaries are reviewed.

## Start locally

Use PowerShell 7 and Docker Desktop. `start-local.ps1` requires an explicitly
reviewed local Chromium-compatible seccomp profile. It does not install or
weaken a host-wide policy or silently disable Chromium's sandbox. The previous
local fixture used profile SHA-256
`EB808EBC38EE27E3A011EE876A38319D22BF09D0C07399650F667FE5DE14B3A1`;
that temporary file is not supplied as a generic production profile.

```powershell
# Run in the SAME shell that will start the local API. Never pass .env to Docker.
& .\deploy\local-url-renderer\start-local.ps1 -SeccompProfile 'C:\absolute\reviewed-profile.json'
$env:URL_RENDER_ENABLED = 'true'
# URL_RENDER_WORKER_URL and the ephemeral TOKEN were set by the script.
.\.venv\Scripts\python.exe -m uvicorn src.backend.main:app --port 8000
```

Stop the old local API before starting another on the same port. The script does
not stop another process, alter `.env`, print the token or activate the worker
on any deployed host. Do not enable the API fallback without the worker URL;
that would select the older in-process opt-in renderer instead. Without opt-in,
behavior is unchanged. If the worker is unavailable, the result stays incomplete
unless other trustworthy danger evidence already exists. Worker configuration
participates in the aggregate cache policy; the access token never does.

For the offline fixture, mount **only** `tests/fixtures/renderer_worker_probe.py`
read-only into the same constrained image, use `--network none` and run that
file instead of the service. The fixture runs real sandboxed Chromium against
controlled synthetic resources; its DNS/resource mocks are not in the worker
image or a production endpoint. This proves local functionality and boundaries,
not access to any live blocked website.

## Evidence and acceptance

Rendered page data returns to the unchanged deterministic/local/Gemini/optional-VT
staged pipeline. A renderer `clean` status means a completed page snapshot,
**not a final safe verdict**. Actual password/OTP/danger signals still escalate.
Denied pages, missing required scripts, timeouts and worker failure cannot
establish a benign result. Static-readable pages never invoke the worker.

Live-site access, end-to-end nine-second performance on a target host, physical
LIFF QR, SF Cinema coverage and production activation remain separate acceptance
items. HTTP 403/503 are not rescued by a whitelist, a VT no-match or invented AI
page content.

### Local observations (2026-10-01)

- Worker image built successfully. Actual runtime inspection verified UID/GID
  10001, read-only root, no provider/Firestore environment, no host bind mounts,
  768 MiB RAM/no swap, one CPU and 128 processes. Chromium sandbox remained on;
  even the dedicated worker token is omitted from Chromium's environment.
- Offline Docker run (`--network none`) used real Chromium with controlled JS:
  ordinary page and password/OTP page snapshots completed, private redirect was
  blocked, and denied/missing-script pages remained insufficient. Latest reader
  durations were 2.777 / 1.020 / 0.896 / 1.154 / 0.975 seconds respectively.
  Snapshot completion is not a benign verdict for the password/OTP case.
- Host verifier -> actual loopback HTTP -> isolated Docker Chromium -> staged
  verdict passed: benign `NO_THREAT_FOUND` with Gemini mock once/VT mock zero
  (3.563 s); password/OTP `SUSPICIOUS` despite VT mock timeout (1.438 s); private
  redirect `INVALID`, no provider mock calls (1.015 s). Providers and lightweight
  source responses were controlled; this was not live AI acceptance or a cached
  shortcut. Earlier run durations were 1.593 / 1.250 / 0.907 seconds, illustrating
  that these samples are not a latency guarantee.
- Real HTTP client timeout/disconnect closed owned browser work: the slot became
  available with zero live Chromium/driver processes in 0.234 seconds after
  disconnect. A cancellation-monitor hang in the initial prototype was fixed
  with cooperative bounded shutdown. A Linux JS private-navigation case also
  exposed lost blocked evidence while awaiting a destroyed DOM; it now exits
  immediately when the blocked target is recorded.
- The ordinary, non-fixture worker read `https://example.com/` once through the
  real public-DNS/IP-pinned/TLS broker: completed snapshot, 917 visible characters,
  3.391 seconds. This tested page acquisition only, **not a final fraud verdict**.
  No live Gemini/VT calls, Firestore/history writes or unknown-URL submissions
  occurred. SF/GunGong were not repeatedly retried or declared fixed.
- Final backend regression: 227 tests passed in 25.050 seconds, including 14
  new worker-boundary/transport tests. One earlier 226-test run failed an existing
  header/body timing fixture; its targeted repeat and final serial suite passed
  without changing that fixture's budgets or assertions.

Temporary fixture/runtime containers were stopped and removed; the local image
is retained. The existing API, `.env`, Render/Vercel/LINE settings and production
renderer opt-in were not changed. No commit, push or paid provisioning occurred.

### Local API activation and live smoke (2026-10-01)

After explicit approval, the ordinary worker was started on numeric loopback
8071 and a separate ordinary API on 8001 with process-only renderer settings.
These were real `/check-fraud` requests, not mocked providers, fixture resources
or a patched verification endpoint. No `user_id` was supplied; normal endpoint
cache/database behavior remained enabled. No arbitrary unknown URL submission
to VirusTotal was enabled. Each target was requested once, without live retries.

| Target | Verdict | Observed provider stages | Elapsed |
| --- | --- | --- | --- |
| `example.com` | `NO_THREAT_FOUND` | Gemini clean; VT skipped | 2.703 s |
| `https://www.youtube.com/` | `NO_THREAT_FOUND` | Gemini and VT skipped; `FAST_SAFE` | 0.891 s |
| `https://squoosh.app/` | `NO_THREAT_FOUND` | Gemini clean; VT skipped | 1.875 s |
| `http://127.0.0.1/` | `INVALID` | Blocked before content fetch; providers skipped | 0.297 s |
| `https://excalidraw.com/` | `NO_THREAT_FOUND` | Isolated worker completed; Gemini clean; VT skipped | 5.797 s |

Squoosh was readable through lightweight HTML, so it did **not** prove browser
fallback. Excalidraw did: `render.source=isolated_local_worker`, render completed,
and `content.source=bounded_rendered_page_evidence`. These are individual live
observations, not a guarantee for all pages or provider response times. Provider
stage statuses are observed here; explicit mock invocation/order assertions
remain in the automated tests. No live malicious-page/VT result is claimed by
this round, and SF/GunGong's previous 403/503 results were not retried or fixed.

After these checks, the specifically identified original localhost API/reload
child was stopped and the ordinary API was restarted on loopback port 8000
with the same isolated-worker process settings. Health returned `ok`; frontend
5173 stayed running and its source was unchanged. Temporary API 8001 was stopped.
The worker `gungong-renderer-local-api` remains running for manual localhost
tests: non-root, read-only, no provider credentials or host bind mounts, 768 MiB
and 128 processes. `.env`, production, Render/Vercel and LINE settings remain
unchanged. This opt-in is **not persistent** across ordinary API restarts; use
the same-shell startup instructions above rather than enabling inline rendering.

Focused renderer/routing/input regressions passed: 57 tests in 1.991 seconds.
No commit, push, cloud deployment or paid provisioning occurred.
