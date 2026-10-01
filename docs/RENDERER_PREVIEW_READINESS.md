# History and isolated renderer Preview readiness

Inspection date: 2026-10-01. Preparation only: no deployment, paid provisioning,
credential transfer, production setting change or Git commit/push in this round.

## History finding and narrow fix

`DatabaseService.save_history` retains the nested `url_check_result`, including
provider evidence supplied by the URL pipeline. `/history/{entry_id}` returns
that full nested record. In contrast, `/cache-entries` intentionally projects
only verdict/completeness from it. `History.handleCardClick` uses the list item
directly, without fetching the full record. The status remains correct, but the
original Thai Gemini explanation is unavailable to the popup.

Reproduced without a database write using all three user-provided responses:
Example, Excalidraw and Everglow. Full-record presentation preserves each Gemini
reason; list-shaped presentation instead selects the generic system explanation.
Ten cache/history contract tests and 33 frontend tests passed, but do not prove
that this list-to-detail gap is resolved. No actual personal History record was
queried in this round; persistence for these specific user scans is unverified.

Implemented after explicit approval: URL/QR History cards load the selected full
record through the existing detail endpoint before displaying the popup. The
list projection stays unchanged; full provider evidence is not sent for every
list entry. Text/bank/phone popups keep their existing no-detail-fetch behavior.
Opening History never invokes Gemini, VirusTotal or `/check-fraud`.

The read has a 12-second deadline, aborts on dismissal/unmount/new selection,
and ignores stale results. A 404, 5xx, network failure or malformed/mismatched
record replaces the loader with a Thai error, not a misleading partial result.
Stored message and explanation remain HTML-escaped. Changes are frontend-only;
no database writes or personal History queries were part of this fix validation.

Real-browser verification used intercepted synthetic list/detail responses:
fresh and cache-hit popups retained the original Thai AI reason and full message;
an HTTP 500 showed the friendly error instead of a stuck loader (with the
expected failed-resource console message). All backend traffic was intercepted;
the fixture supplied only a list and the selected detail endpoints. A separate
automated transport assertion proves one selected-detail GET, with no verifier
or provider call. This proves controlled UI/transport integration, not personal
record persistence. Preview deployment and all cloud gates below remain pending.

Final validation: 49 frontend tests passed (16 new detail-flow tests), targeted
ESLint passed and the frontend production build passed; the existing >500 kB
bundle warning remains. `git diff --check` passed. The test browser was closed,
no personal records were read/written and no live provider quota was consumed.

## Cloud gates

- The current client accepts numeric loopback only. Do not change it to accept
  arbitrary remote URLs. A separate cloud transport needs an explicitly approved
  HTTPS destination policy, TLS verification, no redirects/proxies, dedicated
  service authentication, bounded payloads and the remaining request budget.
- Keep the worker's environment, filesystem and identity isolated from all API,
  Firestore and provider credentials. Do not assume a second service in an API
  project automatically provides that credential boundary.
- Prove the target runtime supports non-root sandboxed Chromium, process/memory
  caps, browser teardown and public-only resource egress. Local Docker flags are
  not evidence that a hosted container has equivalent controls. Never compensate
  with `--no-sandbox`, privileged access or a CAPTCHA/anti-bot bypass.
- Official Vercel container documentation states scale-down after 30 seconds
  idle for Preview and five minutes for production. Therefore another container
  alone does not establish a 12-second first-request guarantee. Measure cold and
  warm end-to-end latency; retain backend 9 seconds / frontend 12 seconds.
- Choose and approve the host/cost/security arrangement before provisioning.
  No hosting plan, always-on purchase, worker project or remote endpoint has
  been selected or created by this preparation.
- Before cutover: protected Preview, real benign JS acquisition, staged provider
  routing, controlled suspicious/private/timeout cases, History detail, physical
  LIFF QR input-only behavior, and Text/Personal/ID-card regressions. Keep existing
  Render/LINE settings available until explicit cutover approval.

## References

- [Vercel container images, ports and scale-in](https://vercel.com/docs/functions/container-images)
- [Service configuration](https://vercel.com/docs/services/config-reference)
- [Local isolation and evidence](LOCAL_RENDERER_WORKER.md)

The Vercel Deployment/Functions skills guided keeping Preview preparation
separate from promotion and requiring target-runtime validation rather than
treating local health/build success as cloud acceptance.
