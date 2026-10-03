# Report submission Service Messages

When explicitly enabled, send a thank-you Service Message immediately after the
server confirms a link/text tip was saved. The tip stays `pending`: acknowledgement
is not review completion. No OA Push, blacklist changes, automatic verdicts or
notifications to administrators are introduced. Manual review never sends another
message.

## LINE Console

Select Checkout / Thai / Answer completed (simple). The supplied Console
screenshot identifies the template as `answer_completed_s_th`, with fixed Thai
wording thanking the user for their cooperation. Add this template with an exact
Use Case: acknowledge a successfully submitted link/text tip in GunGong and thank
the submitting user; the button opens that person's tip receipt and current
status. It does not state that an investigation is complete. Selection and local
tests are not LINE approval; confirm this use case with LINE during review.

Only the required `btn1_url` is sent; this template has no `number` variable or
edit/cancel buttons. The permanent link includes the full 64-character receipt ID.
Do not use the former Application Verified template for submission acknowledgement.

Service Messages appear in LINE MINI App Notice in Thailand, not the GunGong OA.
Unverified MINI Apps can test on the **Developing** internal channel with
Admin/Tester users, not Published. Public release requires MINI App verification
and template approval. Confirm this exact use case with LINE during review.

Sources:

- [Service Message setup and template rules](https://developers.line.biz/en/docs/line-mini-app/develop/service-messages/)
- [Service Message API and single-token restriction](https://developers.line.biz/en/reference/line-mini-app/)
- [Stateless channel token API](https://developers.line.biz/en/reference/messaging-api/nojs/#issue-stateless-channel-access-token)

## Separate Developing configuration

Default flags are off; ordinary submissions and Published login stay unchanged.
Create/configure a separate Developing build/backend, not an unverified Published
deployment. Read its actual internal channel ID, secret and LIFF ID from Console.
Never use the OA bot's channel secret or long-lived access token for this feature.

Server variables (local private environment or deployment secret settings):

```dotenv
LINE_SERVICE_MESSAGES_ENABLED=true
LINE_SERVICE_MESSAGES_ENVIRONMENT=developing
LINE_SERVICE_MESSAGES_PUBLISHED_APPROVED=false
LINE_MINIAPP_CHANNEL_ID=<Developing internal channel ID>
LINE_LOGIN_CHANNEL_ID=<same Developing internal channel ID>
LINE_MINIAPP_CHANNEL_SECRET=<that internal channel's secret>
LINE_MINIAPP_LIFF_ID=<Developing LIFF ID>
LINE_SERVICE_MESSAGES_TEST_USER_IDS=<allowed tester LINE user ID,comma-separated if needed>
```

Public frontend build variables (rebuild after changing; local Vite reads these
from `src/frontend/.env.local`, not the backend's root `.env`):

```dotenv
VITE_LIFF_ID=<same Developing LIFF ID>
VITE_LINE_ENDPOINT_URL=<HTTPS Developing endpoint URL registered in Console>
VITE_LINE_SERVICE_MESSAGES_ENABLED=true
```

The root `.env` is read by backend Settings/CLI when run from repository root;
on deployments use scoped environment settings instead of committing env files.
The frontend endpoint override keeps external-browser login callbacks on the
Developing build instead of returning to the existing Published build. The
callback must be registered for that internal channel in Console. Neither the
LIFF ID nor callback origin can be overridden by URL/query input.

The backend checks channel/LIFF/identity-audience alignment and the Developing
tester allowlist. The allowlist doesn't confer LINE channel roles; those must
also exist in Console. Use the same configuration on the local operator's
machine and the backend. `FIRESTORE_PROJECT_ID` and Firestore IAM credentials
must target the intended database. Client rules must deny direct reads/writes.
Secrets must never enter `VITE_*`, the browser, Git or command arguments.

For a future approved Published release, use that channel's IDs/secret, set
`LINE_SERVICE_MESSAGES_ENVIRONMENT=published` and explicitly set
`LINE_SERVICE_MESSAGES_PUBLISHED_APPROVED=true` only after both approvals.
That flag records the operator's confirmation; it doesn't verify LINE approval.

## Immediate acknowledgement

After displaying a confirmed receipt, the enabled client immediately calls
`POST /api/reports/{id}/notification` with its existing verified LINE bearer.
The backend verifies ownership of the saved tip, then obtains a stateless channel
token, issues/reuses one notification token for that LIFF session and sends
`answer_completed_s_th`. It reuses the same channel token and HTTP client for
issuance and sending (three LINE calls for a new session). No message can be sent
for a missing/foreign tip or before its successful save. A repeated request for
an already acknowledged tip makes no further LINE calls.

This acknowledgement request is separate from saving the tip so LINE latency or
failure cannot undo its receipt or cause the UI to suggest submitting a duplicate.
The UI distinguishes sending, sent, disabled and unavailable/unconfirmed. Keep
the app open until the attempt finishes. Notification failure preserves the tip
and its `pending` status; uncertain delivery is never automatically retried. Tips
that have already been reviewed cannot start a delayed receipt acknowledgement.

The button's permanent link opens `?section=report&reportId=<full-id>`.
The app shows only the signed-in owner's tip/status and any real review result.
Logged-out users must log in; a different owner receives no report data. URLs in
reported content are displayed as text and never automatically opened.

## Optional manual review (no messages)

Review the tip privately in Firestore first. The command does not evaluate its
content. Run from the repository root using an IAM-authorized account; there is
no public review endpoint. `--reviewer` is an audit label, not authentication.
The note is visible to the reporter, so exclude internal/private investigation
details. Choose `risk`, `no_risk_found` (not a guarantee of safety), or `inconclusive`.

Preview only: reads the single record, no database writes or LINE calls:

```powershell
.\.venv\Scripts\python.exe -m scripts.reports.complete_review <full-report-id> --project <project-id> --reviewer <operator-label> --result risk --note "Explanation visible to the reporter"
```

After actual review, explicitly persist the review only:

```powershell
.\.venv\Scripts\python.exe -m scripts.reports.complete_review <full-report-id> --project <project-id> --reviewer <operator-label> --result risk --note "Explanation visible to the reporter" --apply --confirm-reviewed
```

Without `--apply`, this is a read-only preview. The named project must exactly
match configuration. `--apply` requires `--confirm-reviewed`; use the same
result/note/reviewer for an idempotent retry. Conflicting attempts cannot overwrite
a completed review. The old `--notify` option has been removed: the command has
no LINE transport and cannot send a second acknowledgement or a review message.

## Retry, concurrency and sensitive storage

Private collection `report_service_sessions` stores notification tokens, owner,
channel, expiry, remaining quota and durable attempt states. The original LIFF
access token and channel secret/token aren't persisted. The session key is a
SHA-256 digest of channel, verified user ID and high-entropy LIFF access token.
It isn't printed or exposed by report APIs. Protect the collection with backend
IAM and deny-all client rules; notification tokens are sensitive bearer values.
Arrange retention/cleanup of expired session documents according to your policy.
This change does not deploy rules, TTL jobs or grant new IAM permissions.

One session is reused for multiple tips submitted with the same LIFF access
token; issuing a token for every tip would violate LINE's one-token-per-access-
token rule. Sending consumes the shared session quota (initially up to five)
and saves its rotated token. Receipt delivery uses `receipt_notification_state`,
`receipt_notification_claim` and `receipt_notified_at`, separate from any legacy
review delivery fields. An atomic Firestore claim locks both the report and the
shared session, preventing concurrent sends using a stale token. Network
calls are outside transaction callbacks. A zero-quota response is successful
delivery, not a reason to resend.

There is no documented notifier idempotency key. Consequently a send timeout,
lost response, crash after the claim, or failed post-send persistence leaves the
attempt blocked. The submission flow never blindly retries or resets those locks. This
is duplicate avoidance, **not a guarantee of exactly-once delivery**. Some
notifications can remain unsent/unconfirmed and require investigation. Do not
delete/reset attempt records to force retries. Expired/exhausted, missing or
uncertain sessions do not fall back to OA Push. No scheduled retry worker exists.

## Verification

Automated tests use an in-memory transaction model and mocked LINE transport;
they never send real messages or write production records. Live acceptance still
requires configuration and an Admin/Tester test in Developing:

1. Configure the selected template and matching Developing IDs/secret/tester roles.
2. Submit a new tip; confirm its receipt appears before notification finishes.
3. Receive Answer completed (simple) in LINE MINI App Notice immediately after
   successful submission; confirm the saved tip still has status `pending`.
4. Open its detail link and confirm only the submitting account can read it.
5. Repeat the same notification request; confirm no second message is sent.
6. Manually complete review; confirm this sends no further Service Message.
7. Test disabled configuration, another account, expired/exhausted sessions and
   simulated failures. Failure must not lose the saved tip or claim delivery.

No actual secrets, Developing IDs, cloud persistence, LINE approval, delivery or
native LINE rendering are established by local tests alone.
