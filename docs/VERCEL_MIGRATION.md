# Vercel migration preparation

Status: isolated Hobby Preview deployed with explicitly approved provider and
existing Firestore credentials; not a production cutover or acceptance of live
scanning. Project `gungong-vercel-preview` has no Git integration. The complete
local service-account JSON was stored as a sensitive, Preview-only server-side
environment value after explicit user approval; no credential value was printed
or included in source uploads. No LINE credentials or endpoint changes were
introduced. Render, production domain/LINE settings, and existing URL-verification
work remain unchanged; no Git commit or push was made. Vercel automatically built
and published the API image in its own registry as part of the approved test
deployment.

## Deployment shape

`vercel.json` uses the current `services` configuration with two services:

- `web`: Vite at `src/frontend`, built with `npm ci` and `npm run build`, with
  static output in `dist`. The page and assets do not require the API container.
- `api`: the existing root `Dockerfile`. Its Render-compatible frontend build
  is retained, but Vercel routes the public page/assets to `web`, not this image.

Explicit API rewrites precede the frontend catch-all and preserve the original
path: `/check-fraud`, `/history`, `/webhook`, `/api/v2/...`, and the other existing
endpoints stay on one origin. No Render proxy, separate frontend API URL, or
UI/QR behavior change is introduced. `trailingSlash=false` normalizes slashed
URLs before forwarding, preserving POST bodies through a relative 308 redirect.
This avoids the local Services runner's unmatched root endpoint or internal
backend-origin redirect for trailing slashes.

The candidate sets `regions=["sin1"]` for deployment-local API placement near
the approved existing Firestore database in Singapore (`asia-southeast1`). This
does not move the database or change Render. The original Preview ran in `iad1`;
do not rely on the default region for a latency-sensitive database lookup.

Vercel Services and Container Images are currently Beta. Availability and limits
must be checked on the target account before deployment.

## Environment setup (only after deployment approval)

Use `.env.vercel.example` as a reference, not as a file containing real secrets.
The project root is the repository root; do not select only `src/frontend` or
add competing top-level framework/build/output overrides to the services config.

Configure these server-side values in the appropriate Vercel environment:

- `PORT=10000`: required for this candidate. Vercel otherwise expects port 80;
  the existing Dockerfile defaults to 10000 and reads `PORT` at startup.
- `GOOGLE_API_KEY`, `GEMINI_MODEL`: copy the intentionally configured provider
  and model from the existing service, not a newly provisioned account.
- `VIRUSTOTAL_API_KEY`: existing best-effort provider key, if enabled.
- `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_CHANNEL_SECRET`: existing LINE values.
- `FIRESTORE_PROJECT_ID`, `FIRESTORE_DATABASE_ID`: the intended existing project
  and database, checked in your own Firebase/Google console.
- `GOOGLE_SERVICE_ACCOUNT_JSON`: the **complete JSON object**, not a file path,
  base64 string, or individual private key. Preserve the JSON's escaped private
  key newlines. Configure it as a sensitive server-side environment value.

Do not set Render's `/etc/secrets/service-account.json` path on Vercel. Inline
credentials are parsed in memory and passed explicitly to the Firestore client;
no credential file is created. Missing inline credentials retain existing
Application Default Credentials/file behavior for local and Render use. Invalid
inline credentials fail initialization without silently falling back, and the
initialization log does not print the provider exception or key.

Never use a `VITE_` prefix for server secrets or paste them into chat. Disable
Firebase emulator environment variables on a real deployment. Keep
`DEBUG=false`, `SEED_MOCK_DATA=false`, `VIRUSTOTAL_SUBMIT_UNKNOWN_URLS=false`,
`URL_REPUTATION_PROVIDER=disabled`, and `URL_RENDER_ENABLED=false` unless the
specific feature has been separately approved and validated.

`.vercelignore` excludes local credential files, environment files, dependency
directories, generated builds, patches, and test artifacts from source uploads.
The existing `.dockerignore` also excludes secrets from the image build context.

## Safe preview and cutover

1. Review the candidate before linking/importing the repository. Linking a Git
   project can automatically deploy; prefer an explicitly targeted Preview
   deployment without a Git integration for the initial approved test. CLI
   login is still needed to upload the local source; the chat connector's
   read-only team/project access does not authenticate the local CLI.
   Do not rely on `--target preview` alone for a brand-new project: on this
   account, its first upload was assigned `production` despite that flag. That
   deployment was canceled before it became ready or assigned an alias. The
   documented `redeploy <deployment-id> --target preview` workflow produced a
   verified Preview (`target=null`). Inspect the actual target/state after each
   deployment and never promote or change existing domains without approval.
2. After approval, create a preview using an appropriate test Firestore project
   or approved test identity. An ordinary authenticated scan may write History;
   do not assume preview scans against production are read-only.
3. Validate `/`, a built asset, `/health`, API routing, provider configuration,
   Firestore permissions/History, and request deadlines on the actual host.
   Measure an initial request after idle, not just a warm request. If preview
   protection is enabled, use an authenticated browser for tests; LINE webhook
   delivery needs a separately approved externally accessible endpoint.
4. Test QR input-only/manual submit, Text, Check Personal, and Verify/ID Card.
   Test a trusted benign route (Gemini/VT skipped), unknown benign route,
   suspicious escalation, and incomplete/error handling. Local mocks are not
   proof that live providers or target-site access work on Vercel.
5. Only after successful preview validation and explicit cutover approval,
   update LINE LIFF endpoint/webhook URLs and any Firebase Authentication
   authorized-domain/OAuth settings used by the application for the final
   domain. Do not replace those settings with an arbitrary preview URL.
6. Keep Render running/configured until cutover succeeds. Rollback means
   restoring the approved domain/LINE settings to the still-existing Render
   service; no database migration or data deletion is part of this preparation.

## Limits and unresolved URL work

The URL backend deadline remains 9 seconds and the frontend deadline 12 seconds.
These application deadlines do not bound hosting startup before the handler
begins. API containers scale down after idle (currently 5 minutes in production,
30 seconds in preview), so an API cold start can still take time. The static
frontend split removes that dependency from opening the page, not from making
an API request. Hosting latency and timeout behavior after idle still require
measurement on a real Vercel preview; this is **not an always-on API guarantee**.

Moving hosts does not automatically fix SF Cinema's 403 or make JavaScript-only
pages readable. The passive browser fallback stays disabled until the actual
host's Chromium sandbox and resource isolation have been verified. Do not add
`--no-sandbox`, weaken SSRF controls, bypass anti-bot challenges, or mark an
unreadable page safe to make the migration pass. Recent risky evidence remains
subject to the existing URL policy; migration does not redefine verdicts.

## Local evidence (2026-10-01)

- The migration/credential suite now has 15 tests, including discovery of all
  declared backend routes, frontend/API separation, and ignored link artifacts.
  Firestore and provider calls in these tests are mocked.
- Final full serial backend regression: 197 tests passed in 21.865 seconds.
- Frontend: 33 passing tests; targeted ESLint passes.
- Frontend production build passes; existing large-bundle warning remains.
- Existing Dockerfile builds locally as `gungong-vercel-prep-test`.
- Offline container smoke passes: `/`, one built asset, `/health`, and GET
  `/webhook` return 200; an empty POST `/check-fraud` returns the expected JSON
  validation error (422), rather than a frontend page. The container uses UID
  10001, port 10000, no real credentials, and no external network. Local startup
  plus these checks took 5.131 seconds; this is not Vercel startup evidence.
- Configuration validates against the published Vercel schema and rejects a
  deliberately wrong root type. The schema itself declares draft-04 but uses
  newer numeric `exclusiveMinimum` syntax in unrelated trigger definitions, so
  schema self-validation was disabled in the local AJV check. Instance checks
  were retained. This does not substitute for a Vercel preview build.
- Vercel CLI 62.1.0 `dev -L` detected the Vite and container services and built
  the API image on an isolated source snapshot without `.env` or credential
  files. Actual local routing returned 200 for `/`, `/health`, and `/webhook`;
  422 JSON for empty `/check-fraud` and `/api/v2/verify-id-card` requests (with
  and without trailing slashes); and 404 JSON for an unknown `/api/...` path.
- Clean-browser verification: meaningful GunGong content and navigation buttons
  render, no page errors or error overlay. Screenshot:
  `C:\Users\acer\AppData\Local\Temp\clean_tmp\gungong-vercel-home-test.png`.
  This does not test real LIFF authentication or physical QR scanning.
- Frontend-independence test: the disposable API container was paused; the page
  and `/src/main.jsx` still returned 200 while the health request timed out.
  The container was resumed in `finally`; local test processes were then stopped.
- A regression run concurrent with the container build had two timing-sensitive
  fixture failures (shared 0.1-second meta content budget and Chromium startup).
  Both passed in an isolated rerun without changing production deadlines or
  weakening safety assertions. The final full serial run passed all 197 tests.
- `npm ci` reported 19 dependency advisories against the existing frontend
  lockfile. The lockfile and dependency versions were not changed by migration;
  no automatic broad `npm audit fix` was performed. Assess these before
  production cutover, separately from routing/build acceptance.
- Vercel deployment, real environment values, live provider access, and hosting
  startup latency are not validated by these local checks.

## Initial isolated cloud evidence without credentials (2026-10-01)

- Hobby project: `gungong-vercel-preview`, created without Git integration or
  paid upgrades. Source is the dirty candidate based on
  `5a67e7cca91f67b545016f5d46b519769c53d51a`, not a newly committed revision.
- Upload preflight: 136 files / 5,954,262 bytes, with zero credential, environment,
  dependency, or test-artifact files in the upload list. CLI linking generated
  ignored `.vercel/` metadata and a local `.env.local` OIDC token; neither was
  uploaded. Its extra blanket `.env*` ignore was removed so safe example
  templates remain visible.
- First upload: `dpl_9RDT6Pagk4kKPnNf4oSq9aZEsw3E`, automatically classified
  production despite an explicit Preview flag. Verified `CANCELED` with
  `aliasAssigned=false`; it did not become the serving application.
- Actual Preview: `dpl_5cBSv1EjaXQgAabvXutogv5LJQ5C`, verified `READY`,
  `target=null`, with deployment protection retained:
  <https://gungong-vercel-preview-d1f281539-sorravits-projects-31d1c284.vercel.app>.
  Created-to-ready time: 294.922 seconds; container build: 187.3 seconds. The
  cloud build recognized both Vite and container services despite the project's
  top-level framework being `Other`.
- Nonsecret runtime defaults only: `PORT=10000`, debug/seeding/renderer/unknown
  VT submission disabled, extra reputation provider disabled. No environment
  pull or production Firestore identity was used. The protected HTTP test
  generated a project-scoped automation bypass token through the CLI; its value
  was not printed or placed in source.
- Protected HTTP smoke: `/` returned 200 HTML with the GunGong title in 1.310
  seconds; the referenced JS asset returned 200 JavaScript (861,313 bytes) in
  1.014 seconds. The first `/health` returned 200 JSON in 7.106 seconds; the next
  warm health request returned 200 JSON in 0.602 seconds. These are curl network
  durations from this machine, excluding CLI startup, not latency guarantees.
- Empty POSTs to `/check-fraud` and `/api/v2/verify-id-card` returned the expected
  422 JSON missing-field errors (7.228 and 0.353 seconds respectively), proving
  that both root and nested API routes reach FastAPI rather than the frontend.
  No valid scan or history write was performed.
- After an explicit 45-second period without API traffic, `/` still returned
  200 HTML in 0.186 seconds while the next `/health` took 7.479 seconds and
  returned 200 JSON; its warm repeat took 0.355 seconds. This confirms page
  responsiveness after idle in this test, but not an always-warm API. Startup
  is outside the backend's 9-second handler
  deadline and consumes part of the frontend's 12-second request deadline.
  Real first-scan latency with approved test credentials must be measured before
  claiming the migration resolves slow scanning; these smoke tests do not.
- Fresh local regression after linking: 197 backend tests passed in 28.481
  seconds, frontend 33 tests passed, targeted ESLint passed, frontend build
  passed in 11.65 seconds. A sandboxed attempt could not launch the Chrome
  fixtures (nine failures), and esbuild could not read its configuration. The
  same unmodified tests/build passed outside that tool sandbox; no production
  deadline or browser safety assertion was loosened.
- Live Gemini/VT, Firestore/History, LINE/LIFF, mobile QR, and a real browser on
  the protected Preview have not been validated. Do not treat the health endpoint
  as proof that those integrations work. Obtain separate approval for test
  credentials/data before scan requests that could write history.

## Approved existing-database Preview validation (2026-10-01)

- User approved using the existing database, synthetic History records, and
  transferring the complete local service-account key to Vercel Preview.
  `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_API_KEY`, and `VIRUSTOTAL_API_KEY` are
  sensitive values scoped only to Preview. Nonsecret project/database/model
  configuration is also scoped to Preview. No production environment was changed.
- New deployment: `dpl_3QiRAteTi7ce7QVtdRknsL4532ZE`, verified `READY`,
  `target=null`, with deployment protection retained:
  <https://gungong-vercel-preview-934553a2y-sorravits-projects-31d1c284.vercel.app>.
  Created-to-ready duration: 231.380 seconds. Source remains the dirty candidate
  based on `5a67e7cca91f67b545016f5d46b519769c53d51a`; both services built.
  Upload preflight contained 136 files / 5,958,590 bytes and zero forbidden
  credential, environment, dependency, or test-artifact source paths.
- Runtime defaults still disable mock seeding, debug mode, browser fallback,
  unknown-URL VT submission, and the extra reputation provider. No new external
  account or paid integration was provisioned.
- First protected `/health`: 200 in 8.339 seconds. Reading a deliberately
  nonexistent synthetic History document returned 404 in 1.417 seconds rather
  than database-not-configured or permission errors, proving real Firestore read
  access without fetching another user's data.
- One cache-miss `/check-fraud` for an `example.com` URL with a unique test query
  and synthetic user identity returned 200 in 13.124 seconds. The verifier reported
  2.2178 seconds (not total handler or hosting duration). Redirect/content were
  clean with readable page evidence. Gemini `gemini-3.5-flash-lite` returned clean
  evidence and a Thai explanation. VT returned `not_found`; submission was
  disabled. This proves live provider access, not a clean overall verdict, nor
  an exact count of SDK-level HTTP attempts.
- Overall result was correctly `INCOMPLETE` / `CORE_FAILURE` because required
  recent-risk lookup hit the configured 1.0-second RPC deadline
  (`DeadlineExceeded`, 1003 ms). VT's `not_found` did not substitute for the missing
  core evidence. The result was not eligible for a long-lived clean cache.
  Do not remove this required check or relabel incomplete evidence as safe.
- A filtered query for only the synthetic test identity returned 200 in 8.788
  seconds and exactly one persisted History record: type `link`, verdict
  `INCOMPLETE`, with `is_safe` and `is_fraud` null. The authorized synthetic record
  remains in the existing database; no user data was deleted or modified.
- Fresh credential/config tests: 15 passed; frontend: 33 passed; targeted ESLint
  and `git diff --check` passed. No application-source change was needed in this
  validation step; the architecture note records actual cloud evidence.
- Production acceptance is still blocked: the measured scan exceeded the
  frontend's 12-second limit, and required Firestore risk lookup timed out even
  though credentials and History persistence work. No repeated live URL/provider
  retries were performed. Hosting startup and cross-region database latency need
  a separate measured fix before cutover; health success alone is not acceptance.
  LINE/LIFF, physical mobile QR, all other scanner flows, and production traffic
  remain unvalidated on this protected deployment. Keep Render available.

## Region and startup follow-up (2026-10-01)

- Read-only database metadata confirmed `asia-southeast1`; the preceding
  Preview and project default were `iad1`. Set only the candidate deployment's
  region to `sin1`, without changing project-wide production settings or moving
  any data. The new deployment API confirmed `regions=["sin1"]`.
- Import profiling showed the API eagerly loading sklearn for message similarity
  even on URL requests. Deferred sklearn/numpy imports in fraud-message
  deduplication and similarity calculations until those features actually need
  vectors. No algorithm, threshold, Text routing, OCR, or URL verdict changed.
  A fresh interpreter test imports the entire app and asserts sklearn is absent;
  numerical tests still exercise real TF-IDF and cosine similarity on mocked
  database data. Local cold import changed from 4.939 to 2.542 seconds in these
  samples, not a cloud startup guarantee.
- Deployment: `dpl_EHuy8Joen8Cm1uXRF7oKHbXvG1bW`, verified `READY`, Preview
  (`target=null`), protected, region `sin1`:
  <https://gungong-vercel-preview-jowfh8alg-sorravits-projects-31d1c284.vercel.app>.
  Created-to-ready: 228.713 seconds. Frameworks remain Vite and the existing
  Docker container; source is the dirty `5a67e7cca91f67b545016f5d46b519769c53d51a`
  candidate. Upload: 136 files / 5,962,641 bytes, zero forbidden source paths.
- First API request was a cache-miss example.com scan with a unique query, not
  a preparatory health request: 200, `NO_THREAT_FOUND`, `AI_CONFIRMATION`, in
  **12.441 seconds total**. Required risk history was `not_listed`/complete,
  readable content and local checks completed, Gemini returned clean Thai
  evidence, and VT was `skipped_not_needed`. The verifier alone took 2.3909
  seconds. The previous Firestore deadline failure was not reproduced in any of
  this candidate's three live scans; budgets/retries were not increased or
  bypassed. This is sampled evidence, not a reliability guarantee.
- YouTube root: 200, cache miss, `NO_THREAT_FOUND`, `FAST_SAFE`, in 10.255 seconds
  total; verifier 0.388 seconds. Both Gemini and VT were `skipped_not_needed`.
  Live structured logs confirm routing, and deterministic tests assert actual
  provider call counts. No hostname-specific safe bypass was added.
- Mandatory `https://qr1.be/ET2MJ2`: 200, cache miss, followed one redirect to
  `https://www.nectapharma.com/`, assessed readable final-page evidence, and
  returned `NO_THREAT_FOUND` / `AI_CONFIRMATION` in 3.691 seconds total (verifier
  2.9515 seconds). Gemini was clean; VT skipped. This observation applies to this
  URL at this time, not every qr1.be link or a permanent destination assertion.
- Filtered History query for only this round's synthetic identity returned one
  persisted record: type `link`, `NO_THREAT_FOUND`, complete, `is_safe=true`,
  `is_fraud=false`. Query duration 8.763 seconds after idle. Across both approved
  credential-validation rounds, two synthetic History records remain; no real
  user's History was queried, deleted, or modified.
- Runtime logs show a new server process on the first example scan, YouTube
  after idle, and History after idle. Request timestamps preceded app startup
  completion by roughly 9.57, 9.42, and 8.33 seconds respectively. These intervals
  include hosting scheduling/image/startup overhead and cannot all be attributed
  to Python imports. The warm qr1.be request did not start a new process.
- Final backend regression: **201 tests passed in 27.179 seconds**. Initial runs
  each had one timing-sensitive fixture failure: Chromium navigation in the first
  run concurrent with frontend build, then shared meta-refresh content budget in
  the serial run. The former passed separately. The latter's mock delays now
  leave first-hop scheduling headroom and make each individual body fit a fresh
  budget while their sum exceeds the single shared budget; this strengthens the
  reset-budget regression rather than increasing production timeouts. All
  deadlines, assertions, and browser sandbox requirements are retained.
- Frontend: 33 tests passed; targeted ESLint passed; production build passed in
  12.11 seconds with the existing large-bundle warning. No frontend or Dockerfile
  change was made in this follow-up. No live VT quota was consumed by these
  three scans because all three routes correctly skipped it.
- **Not production-ready for the strict 12-second first-request contract:** the
  example scan still exceeded that limit, and an uncertain 9-second handler plus
  a cold container cannot be guaranteed to fit it. Do not extend the frontend
  timer or introduce background keepalive traffic to claim acceptance. Container
  scale-down after idle is documented platform behavior. Further work requiring
  a different hosting/runtime arrangement, an always-on API, or a paid plan
  needs an explicit user choice/approval; no such service was provisioned.
  Mobile LIFF/physical QR acceptance and production cutover remain outstanding.
  Render, LINE settings, credentials, and Git history remain unchanged.

## Current official references

- [Services](https://vercel.com/docs/services)
- [Service configuration](https://vercel.com/docs/services/config-reference)
- [Routing and original-path preservation](https://vercel.com/docs/services/routing)
- [Container images, ports, scaling, and limits](https://vercel.com/docs/functions/container-images)
- [Function region configuration](https://vercel.com/docs/functions/configuring-functions/region)
- [Singapore region identifier](https://vercel.com/docs/regions)
