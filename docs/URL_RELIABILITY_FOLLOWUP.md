# URL reliability follow-up: v5 candidate

## What this changes (not an accuracy guarantee)

The staged fast path and unknown-origin Gemini confirmation remain. Ordinary
same-origin password forms alone are no longer deterministic phishing evidence.
Bank credential requests, OTP/urgency, credential collection off-origin, authority
payment coercion and gambling evidence still escalate. News wording cannot
suppress an actual bank/password collection form. Gemini cannot self-certify
empty/interstitial input as sufficient or claim official ownership from a domain.

A completed VT report with one malicious engine becomes `SUSPICIOUS` in **URL
mode**, retaining `provider_status=malicious`, counts and source details. Multiple
malicious engines retain `MALICIOUS`. This is an explicit conservative routing
policy, not a calibrated accuracy percentage or a claim that engines are
independent. VT's raw provider API and text/SMS classifications are unchanged.
No zero-scanner/all-failed/malformed result counts as clean. Completed provider
lookups are cached for five minutes, not seven days; provider report analysis
time is retained when supplied. Missing detections never prove harmlessness.

## Cross-request risk memory

`url_risk_evidence` is a backend-owned, positive-only store keyed by SHA-256 of
the normalized **exact URL**. No query strings or page bodies are stored in this
collection. Completed newly obtained risk evidence is saved even if required
page checks failed. Original scan URLs are guarded; final destinations receive
only evidence applicable to them. Query/path distinctions remain intentional:
do not strip arbitrary parameters or label an entire shared domain malicious.

Weak VT evidence has a maximum 15-minute lifetime, other newly obtained risk
evidence a maximum one-hour lifetime. An explicit provider expiry shortens these
limits. Reads enforce expiry without deleting user data. Inherited/cached
observations do not renew the lifetime. A retained observation is a temporary
`SUSPICIOUS` guard requiring confirmation, not a permanent malicious label.
Current malicious evidence still dominates. A clean page/AI assessment or a
cached benign result cannot erase an active guard; optional VT failure cannot
turn it into safe. Guard-read failure means incomplete, not a benign fast path.

All aggregate cache hits consult the guard before returning a benign result.
Inherited risk is not written into aggregate cache. Aggregate benign cache has a
maximum one-day lifetime; aggregate risk cache a maximum 15-minute lifetime,
both capped by applicable provider expiry. v4 aggregate entries are ignored;
historical entries are not edited, and past observations are not automatically
migrated into the new store. The positive store must not allow frontend writes;
deployment IAM/Firestore rules remain an operator responsibility. Writes are
best-effort: failures are logged without sensitive details and are not silently
represented as successful persistence.

Requests also retain a bounded expiring guard in process memory if persistence
fails or the remaining deadline cannot accommodate a write. This fallback is
not durable across restarts or shared across instances. Positive writes use
create/compare-and-set without retry, and do not shorten an existing longer
live observation. This is not an atomic transaction across
guard reads, external analysis and later cache writes; it is not a global
cross-instance serialization guarantee.

Guard reads have a dedicated 1.0-second native timeout with retries disabled and
a 1.2-second stage cap; guard writes retain a 0.5-second timeout per RPC. Cache
reads are offloaded and bounded; they do not perform stats or
expiry writes inline in URL mode.
URL cache-hit statistics are recorded separately after response in production.
Cache/guard lookup and verification share the
nine-second request budget; frontend remains twelve seconds. Already completed
risk evidence survives deadlines. History/cache writes retain their existing
post-response workflow in production.

Cancellation cannot forcibly stop a running synchronous Firestore RPC; native
RPCs have retries disabled and bounded timeouts (a positive compare-and-set can
use one read and one write). Such a write can finish after its async caller has
timed out. The in-process fallback does not assert that the durable write failed
or succeeded when the outcome is unknown.

## Readability and presentation

HTML with an incorrect Content-Type can be recognized using a bounded prefix;
unsupported binary content stops at a small sniff. Declared text charsets are
decoded without treating replacement noise as usable evidence. Mislabelled HTML
meta redirects still use the same per-hop SSRF validation, loop/hop limits,
TLS checks, byte cap and total deadline. This does not execute JavaScript or
bypass CAPTCHA/access controls. Logs/results include HTTP status and MIME type,
not page bodies or sensitive query strings.

An incomplete result remains neither benign nor detected danger. Scanner shows
a neutral information icon, Thai "ยังประเมินไม่ได้" instead of `Unknown`, and
explains that insufficient checks do not mean danger was found. URL History
uses verdict metadata rather than treating every non-safe value as dangerous;
URL Gemini confidence is not presented as a safety percentage. The list query
projects only verdict/completeness, not full URLs or provider payloads.

## Optional Google threat-list evidence

Disabled by default. No service activation, billing change, provider request or
Gemini-key reuse occurs unless explicitly configured:

```
URL_REPUTATION_PROVIDER=disabled   # or safe_browsing / web_risk
URL_REPUTATION_API_KEY=<separate server-side key>
```

Enable only after reviewing the product's permitted usage, warning/attribution
requirements, privacy and billing. Lookup sends the URL to Google. Safe Browsing
is for eligible non-commercial usage; Web Risk is the commercial alternative.
This candidate adds the server adapter, not a claim of production activation or
an assertion that all product/redistribution terms have been satisfied.

The optional provider runs within the core stage after safe redirect resolution,
on original and final URL. When enabled it is required and capped at one second,
also bounded by the remaining global budget. `not_listed` is not positive benign
evidence and cannot replace readable content. A positive match dominates; errors,
429 and timeouts are incomplete. Google cache expiration is honored, including
when copying evidence into persistent caches. No aggressive retries occur.

Official references:

- [Safe Browsing v5 URL lookup](https://developers.google.com/safe-browsing/reference/rest/v5/urls/search)
- [Safe Browsing permitted use](https://developers.google.com/safe-browsing/reference)
- [Web Risk lookup and match expiry](https://docs.cloud.google.com/web-risk/docs/reference/rest/v1/uris/search)
- [VT URL scanner categories](https://docs.virustotal.com/reference/url-object)

## Actual live readability observation: 2026-10-01

One bounded DNS/HTTP/content-only attempt per exact user-supplied URL; no AI,
VT, database writes, JavaScript execution or retry:

- codex-resets: HTTP 200, readable HTML, 174,557 bytes, 4,096 bounded visible text
  characters, no deterministic signals, 0.860 seconds. This is **core content
  evidence only**, not a full final verdict or proof of legitimacy.
- SF Cinema: HTTP 403, no readable preview, 0.250 seconds. The server refused
  this automated request. The original incident lacked HTTP metadata; this
  current observation does not prove all earlier failures were also HTTP 403.

**The live SF Cinema acceptance case is not resolved by parser changes.** No
origin-specific allow-safe exception was added. A threat-list miss or AI claim
does not bypass this missing content. A separate authorized rendering/data
source may improve coverage, but no background browser worker or asynchronous
rescan UI has been implemented in this candidate. Such a worker needs isolated
egress, per-resource SSRF protection, bounded lifecycle/concurrency and a clear
access/privacy policy; do not move Chromium into this interactive request.

The existing DNS-validation-to-connection rebinding limitation remains;
production needs outbound restrictions or address-pinned connections. No SSRF,
TLS, redirect or evidence-sufficiency control was disabled for these URLs.

## Expanded smoke tests and bounded fixes: 2026-10-01

A new-process first risk-history RPC reproduced `DeadlineExceeded` after 0.531
seconds with the former 0.5-second timeout; a different subsequent read completed
in 0.125 seconds. This is an observed first-read deadline failure, not proof that
every failure is authentication setup. Risk reads now use 1.0 seconds inside a
1.2-second stage cap. Errors remain incomplete and expose only sanitized type,
budget and elapsed diagnostics. Write budgets/retries did not change.

Native meta-page body time was previously charged to both content and transition
budgets. Body reads now share one two-second budget across meta pages without
double-charging header/DNS time; neither budget resets on a redirect. The header/
DNS/transition allowance is three seconds, combined resolver at most five seconds,
always inside the unchanged nine-second verifier and twelve-second frontend cap.
Slower providers receive only remaining time, not an additional full budget.

HTTP clients identify the bot and its project URL with the configurable
`URL_FETCH_USER_AGENT`; they do not impersonate browsers, rotate identities or
retry denied pages. This follows the [Wikimedia User-Agent guidance](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy).
The observed Wikipedia 403 changed to HTTP 200 after this update in one final
verification attempt. That temporal observation is not proof that all 403s have
the same cause. SF Cinema still denied access; no domain exception was added.

Final native-verifier observations, no aggregate cache or DB writes:

| URL | Verdict | Seconds | Gemini / native VT invocations |
| --- | --- | ---: | ---: |
| https://www.youtube.com/ (first case in a new process) | NO_THREAT_FOUND | 2.484 | 0 / 0 |
| https://www.wikipedia.org/ | NO_THREAT_FOUND | 0.766 | 0 / 0 |
| https://www.python.org/ | NO_THREAT_FOUND | 2.047 | 1 / 0 |
| https://qr1.be/ET2MJ2 | NO_THREAT_FOUND | 3.421 | 1 / 0 |
| User-supplied SF Cinema showtime URL | INCOMPLETE | 2.360 | 1 / 1 |

QR's observed final host was `www.nectapharma.com`, one meta redirect; it was
resolved and its readable page assessed, not hardcoded. Earlier bounded attempts
timed out, including one after the double-charge fix with the then-two-second
header budget. The final pass does not guarantee future remote-site timings.
SF returned HTTP 403; Gemini was uncertain and native VT was not_found. No-match
does not compensate unreadable content, so this live acceptance case remains
unresolved. All five final calls finished below nine seconds; this was a local
service-level test, not an HTTP endpoint/UI/Render deployment measurement.

The expanded matrix before the final header-budget/User-Agent adjustment also
assessed Python documentation, GitHub login, GOV.UK, W3C standards and BBC news.
Each produced NO_THREAT_FOUND with one Gemini invocation and zero VT invocations
in 1.672–2.390 seconds. GitHub's ordinary password form did not create automatic
risk. Those five pages were not fetched again after the final adjustment. They
are spot checks, not a representative labelled accuracy corpus.

Each live phase capped native VT lookups at two and prohibited submissions of
unknown URLs; the cap was not reached in these expanded/final phases. Native
invocation counters do not assert SDK-internal HTTP attempt counts. Controlled
fake-bank/OTP, malicious, redirect-private and deadline cases remain automated
mock tests, not claims about live malicious-site detection. No Google provider
activation, Firestore/history/cache writes, commits or push occurred.

Automated fixtures cover generic origins and the two supplied hostname shapes
with controlled benign HTML, provider counts, risk-cache replay, positive expiry,
normal login, phishing controls, malformed/failed providers, and deadlines. These
are regression proofs, not measured real-world false-positive/false-negative
rates. Establish those rates with a labelled, representative held-out corpus
and report benign coverage, malicious recall, false alarms, incomplete rate and
latency separately before claiming any accuracy target.

## v6: SPA evidence candidate, not a completed production fix

The supplied GunGong response had HTTP 200 but zero visible text because React
had not run. This is different from SF Cinema's HTTP 403 access denial. No
hostname exception or domain-only benign return was added.

`URL_RENDER_ENABLED=false` by default. An explicit deployment opt-in enables
the generic fallback for insufficient readable HTTP 2xx pages. Completed
lightweight HTML is reused (including its CSP), avoiding a duplicate fetch.
Rendered body text plus structural form evidence then goes through the SAME
deterministic, local-reputation, Gemini and optional-VT staged routing. Changed
JS destinations are recorded and their recent-risk/local evidence rechecked.
Readable static pages and existing danger findings do not launch Chromium.
Denied 403 pages are not repeatedly fetched or bypassed.

The browser uses fresh anonymous contexts, mandatory Chromium sandboxing,
blocked service workers/WebSockets/downloads, no form submissions/POSTs, and
no forwarded credentials/cookies. HTTP resources are fulfilled by a broker
that rejects every non-public DNS answer and connects to a validated IP with
the original TLS hostname/SNI. A deny-all local proxy and disabled browser DNS
cover network paths outside routing; this is defense in depth, not a proof
against browser exploits. Original lightweight HTTPX fetching retains the
previous documented DNS-rebinding limitation; the pinned broker does not
retroactively eliminate it. Browser rendering MUST have separate deployment
resource isolation/limits before use on attacker-controlled URLs.

Two concurrent render jobs are permitted; excess jobs return unavailable,
not an unbounded queue. Startup/resources/DOM readiness share up to 4 seconds inside
the 9-second global envelope, with 1.8 seconds reserved for cleanup when
selecting the render budget. Individual resources are capped at 3 MiB, combined
resources at 8 MiB, and requests at 40. Positive actual page text is required;
HTTP 200, optional telemetry failure, no-match reputation or a skipped provider
is not positive benign evidence. Main documents/scripts/styles and same-origin
data remain required. Failed third-party telemetry/auth data is recorded as
optional, not as a failure to read a public page; that distinction does not
claim verification of login, authenticated or transactional flows. Delayed JS,
interactions, hidden content, complex workers, non-passive apps and content
beyond the bounded snapshot are outside scope. There is no CAPTCHA/stealth
bypass and no TLS certificate-verification disablement.

Native AI danger now requires a bounded verbatim risk quote from supplied page
evidence. Claims of credential theft/impersonation without an actual password
or OTP field are uncertainty, not established danger. Free hosting, unfamiliar
origins, privacy notices and security-tool examples are explicitly not proof of
fraud. This guard can abstain on other attack shapes; VT/local deterministic
evidence remains authoritative and is never weakened by an AI abstention.
Grounding is not an accuracy guarantee; a model can still misinterpret a real
quote. v5 cache entries are not reused as v6 completed proof; renderer opt-in
also participates in the cache policy key. Incomplete results remain uncached
as long-lived benign results. Existing positive-risk records are not deleted.

Local candidate observations on 2026-10-01 bypassed aggregate cache and made no
Firestore/history writes or unknown-URL submissions. Before the final seed and
AI structural guards, the expanded final matrix was:

| Public page | Verdict | Seconds | Gemini / native VT invocations |
| --- | --- | ---: | ---: |
| GunGong | INCOMPLETE (render timed out) | 8.422 | 1 / 1 |
| YouTube | NO_THREAT_FOUND | 1.984 | 0 / 0 |
| React documentation | NO_THREAT_FOUND | 1.985 | 1 / 0 |
| Python documentation | NO_THREAT_FOUND | 2.031 | 1 / 0 |
| Vue documentation | NO_THREAT_FOUND | 1.859 | 1 / 0 |
| GitHub login | NO_THREAT_FOUND | 1.969 | 1 / 0 |
| qr1.be/ET2MJ2 | NO_THREAT_FOUND | 4.984 | 1 / 0 |
| SF Cinema showtime (tracking parameter omitted) | INCOMPLETE (HTTP 403) | 2.985 | 1 / 1 |

QR's destination was observed at runtime as `www.nectapharma.com`, not
hardcoded. Reusing the completed HTML subsequently made GunGong's actual core
readable (2,291 visible characters, no deterministic suspicious signals), but
Gemini still made an unsupported fake-form claim. The final structural guard
was added for that failure. This is not evidence of a successful GunGong benign
acceptance; neither GunGong nor SF may be declared production PASS.
The subsequent final native attempt still returned INCOMPLETE after a render
timeout, at 9.016 seconds including scheduling/cancellation overhead. A
controlled test run under concurrent browser load also exposed overly short
driver cleanup allowances. Cleanup was subsequently lengthened/reserved and
the verifier's nested render timer removed; native acceptance after that change
has not been claimed. Live retries were stopped rather than selecting a passing
remote-site timing. The latest implementation remains an opt-in candidate.

Docker image build succeeded, but the non-root sandboxed fixture failed with
`No usable sandbox!` under Docker Desktop's default security profile. Browser
installation alone is insufficient. No `--no-sandbox`, privileged container,
SYS_ADMIN capability, production security-policy change, deployment or paid
provider activation was performed. Follow the official
[Playwright non-root/seccomp guidance](https://playwright.dev/python/docs/docker)
and verify the actual hosting environment; do not assume Render supports the
necessary settings. A separately resource-isolated sandbox-capable renderer
or suitable managed service needs an explicit infrastructure/privacy decision.
403 coverage likewise needs a permitted content source or other sufficiently
strong evidence, not repeated retries or treating VT not_found as safe.

Final regression after cleanup/seed/CSP/hash fixes: 175 backend tests passed,
including 27 renderer/routing/grounding tests and unchanged ID-card regressions;
33 frontend tests passed. Targeted frontend ESLint, frontend production build,
and whitespace checks passed. Earlier concurrent-load test failures were not
hidden; the final backend run had no live browser job competing with fixtures.
These are functional regression results, not a production performance or
accuracy acceptance. Browser runtime on a sandbox-capable isolated host, SF
coverage and a successful native GunGong benign verdict remain outstanding.

### Follow-up: local sandbox compatibility and bounded compressed resources

On 2026-10-01, the Playwright v1.63.0 example seccomp file failed before the
fixture started under Docker Desktop 29.0.1 (`openat2` compatibility error).
A **temporary local-only** profile based on Moby's current default seccomp rules
plus `clone`, `setns`, `unshare` and `chroot` allowances ran the intercepted
synthetic SPA successfully with `chromium_sandbox=True`. The additional chroot
allowance is needed by Chromium inside its new user namespace when container
capabilities are all dropped. No host capabilities were added. The test used
non-root UID 10001, `--network none`, `--init`, `--cap-drop ALL`,
`no-new-privileges`, 768 MiB memory/no swap, one CPU, 128 processes and a private
128 MiB shared-memory allocation. No host IPC, privileged mode, SYS_ADMIN or
sandbox-disable switch was used. This is an offline fixture, not a deployment
security certification or a production-host compatibility proof.

The generated temporary profile SHA-256 is
`EB808EBC38EE27E3A011EE876A38319D22BF09D0C07399650F667FE5DE14B3A1`.
It is not installed into Render or included as a production configuration.
Any production renderer needs a compatible, resource-isolated runtime and
egress policy; it must not inherit service credentials or expose a public
browser-control endpoint. Keep rendering disabled until that boundary is
established and verified. See [Playwright Docker guidance](https://playwright.dev/python/docs/docker)
and [Docker seccomp documentation](https://docs.docker.com/engine/security/seccomp/).

The resource broker now accepts single gzip/deflate streams even if a server
compresses despite `Accept-Encoding: identity`. Both wire and decoded bytes are
capped by the existing resource budget; decompression is incremental with a
bounded output length. Truncated, corrupt, concatenated or trailing encoded
streams, unsupported/stacked encodings and oversized decoded bodies fail
closed. Seven regression tests cover these cases. No new dependency, quota,
provider, website exception or larger global timeout was introduced.

One further read-only native GunGong verification, with local renderer opt-in,
returned `INCOMPLETE` in 3.672 seconds: the origin answered **HTTP 503**, so no
SPA renderer ran. Gemini returned uncertain (one invocation) and VT returned
not_found (one invocation); no Firestore/history/cache writes or URL uploads
occurred. No retry was made. This is a remote availability observation, not a
new proof of page readability, benign intent or a resolved GunGong acceptance
case. SF's previously observed access denial likewise remains unresolved.

Final validation of this follow-up: 182 backend tests and 33 frontend tests
passed; targeted frontend ESLint, production frontend build and
`git diff --check` passed. The only frontend build warning remains the existing
large output chunk. The current Docker image built successfully; the same
resource-limited, offline fixture asserted completed rendered text with no
missing resources in 1.634 seconds (renderer call, not container startup or
the full verification endpoint). Image manifest list digest:
`3fd906c0877d9cae2757b8cf0433ebb169fd9c47762456a274665ec3524d4749`.
These results do not turn the unresolved live cases into a production PASS.
