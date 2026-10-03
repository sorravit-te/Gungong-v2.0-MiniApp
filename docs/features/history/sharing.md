# History sharing (LINE Share Target Picker)

User story: choose one personal scan → consent → create a limited snapshot → preview exact shared fields → select friends/groups in LINE → recipient opens the snapshot detail page.

## Configuration / release

- Enable `shareTargetPicker` and accept its agreement in the MINI App channel's Web app settings. Confirm the Published Data setting. Custom sharing works for unverified and verified MINI Apps, unlike production Service Messages.
- The deployed frontend's existing `VITE_LIFF_ID` and `VITE_LINE_ENDPOINT_URL` must match that build's internal channel. Production uses Published values; do not promote a Developing-configured build or replace Published with Developing IDs.
- No new secrets, Service Message flags or message templates. Sharing does not use a Service notification token.
- Release frontend and backend together, then test from the Published MINI App on a real phone. This document does not prove deployment, LINE Console enablement or actual LINE message delivery.

## Data / access boundary

- POST `/api/history-shares`: authenticated owner of `entry_id` only, explicit `consent: true`, optional `include_content`, 256-bit client-generated random `token`. Body limited to 32 KiB, schema rejects extra fields. The server reads the owned record and constructs the snapshot; it never trusts caller-provided results/identity/expiry.
- The immutable snapshot contains type, aggregate verdict, scan time, and optionally a 240-character content excerpt. Common long numbers/emails are masked; bank/phone show only the final four digits. HTTP(S) URLs show hostnames only, without credentials, path, query or fragment. This is data minimization, **not guaranteed anonymization**. Users must review the preview; arbitrary free text may still identify someone.
- Original History is never public, changed or copied wholesale. No profile, UID, History ID, raw AI reasoning, provider evidence or access token is in the public projection.
- A link uses `https://miniapp.line.me/<build-LIFF-ID>#share=<token>`; fragment does not reach the frontend host's HTTP request or referrer. Any person with the link can read/forward it. It is not restricted to the particular recipients selected in LINE.
- Server stores only SHA256(token) as the `history_shares` document ID, plus private ownership metadata and the snapshot. No public listing/query API or direct Firestore client access. Existing deny-all client rules remain unchanged.
- Expiry is checked by the API at every read (7 days); Firestore TTL cleanup is **optional and not required for access expiry**. Expired stored documents are not automatically deleted by this patch.
- POST `/api/history-shares/<token>/revoke` requires the owner, marks revoked, and never reopens or extends an old link. Retries using the same token are idempotent and cannot change the snapshot or extend the expiry.
- The same prepared link is retained only in the mounted History page's memory; closing/reopening that dialog reuses it. Refresh/navigation loses this UI handle. The owner may revoke from the preview while it is available, or via the authenticated revoke API with the saved link token. There is no durable share-management dashboard in this version.
- Stopping a link cannot erase an already sent LINE card or screenshots. The detail API is `private, no-store`, `noindex, nofollow`; the standalone page sets no-index and no-referrer. Avoid logging bearer tokens in API access logs/observability exports (token is still in the API path).
- Local rate limits: create/revoke 10/min/IP, detail 60/min/IP. In-memory limits are per process, **not distributed infrastructure-wide limits**.

## Speed and interaction

- Opening the dialog is immediate and makes no write. After consent, initial preparation needs one owner-auth check, one History document read and one snapshot create; no extra detail fetch, AI scan, LINE service-message calls or audience-token issuance.
- The preview renders the server's exact minimized snapshot. The next explicit click calls `shareTargetPicker` synchronously before any network await, retaining the user gesture for external-browser popups.
- During preparation/action, show a spinner and prevent duplicate clicks. A failed/uncertain write retries the same token, never automatically creates another link or resends a LINE message.
- Successful picker result and cancellation are separate. Cancellation leaves the prepared link active until revoked/expired; it does not claim message delivery. Errors never show raw provider response bodies.
- The main app and its styles load eagerly, preserving the existing refresh behavior without an extra whole-app Suspense screen. Only the shared detail page is lazy-loaded. Recipients therefore download the main app code too, but do not mount its personal app/AuthProvider, fetch private History or Community, or show the PDPA modal. They read only one snapshot document. LIFF callback restoration happens independently; this does not remove LINE's own consent/login UI when opening a MINI App.
- Actual cloud/mobile latency has not been measured; cold starts, network and LINE behavior still affect timing.

## Acceptance

1. On Published, open History and choose a card's Share button: no detail popup triggered underneath.
2. Without consent, no write. Optionally exclude the content; inspect the prepared preview. Test safe, risk, incomplete and invalid verdicts.
3. Select a different LINE account/group. Verify the Bubble card, branding footer and detail button. Recipient sees this result only; private History remains inaccessible.
4. Cancel picker: no success toast/resend. Reopen preview: reuse prepared link. Revoke: old detail URL no longer loads.
5. Unknown/expired/revoked links have the same unavailable result. Slow/offline requests show feedback and allow bounded retries; no false success.

References: [LINE custom share format](https://developers.line.biz/en/docs/line-mini-app/develop/share-messages/), [LIFF shareTargetPicker](https://developers.line.biz/en/reference/liff/#share-target-picker), [permanent links](https://developers.line.biz/en/docs/line-mini-app/develop/permanent-links/).
