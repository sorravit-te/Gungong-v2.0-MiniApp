# Content reports

Navigation order: Home, Community, Scanner, History, Report. Verify and its ID-card
scanner remain in source but are not active application routes.

The Report page accepts HTTP(S) links (including URLs decoded from QR codes) or
message text, a reason, and optional context. LINE login is required to submit.
This is a tip submission, not a police complaint or a public Community post.

Link reports and Scanner share QR camera/image controls. Images (JPG, PNG, WebP,
up to 10 MiB) are decoded locally using jsQR in a bounded worker; image bytes are
not uploaded. Only a valid HTTP(S) URL fills the input, without automatically
checking the URL or submitting a report. Missing QR codes and unreadable images
show inline errors. Editing the input or leaving the page cancels stale reads.

POST /api/reports uses the existing server-verified identity dependency. It stores
append-only records in Firestore collection content_reports, with reporter_id,
kind, content, reason, details, request_id, created_at, and status pending.
Only a confirmed write or a matching previous write returns a receipt.

The request UUID is reused after uncertain responses, and the document key is a
hash of verified user ID plus UUID. Atomic create prevents duplicate writes;
reusing an ID for different content returns 409. URL tips are never fetched.
Limits: link 2048 characters, text 5000, context 1000, body 32 KiB, 5 requests/minute
per client IP. GET /api/reports/{id} is an authenticated owner-only detail endpoint;
no public read/list endpoint is provided. It excludes tokens, session keys,
operator identifiers and internal delivery state.

Tips do not automatically enter any blacklist, modify scan results, trigger AI
training, or send administrator notifications. Review is manual; there is no
moderation dashboard or automated review worker. When explicitly enabled, the
authenticated flow sends an Answer completed (simple) MINI App Service Message
immediately after a confirmed submission, thanking the reporter. The tip remains
pending; receipt acknowledgement does not mean it has been reviewed. The local
operator command records completion after actual review and never sends messages.
See [Service Messages](service-messages.md) for setup and safeguards.

The production policy file config/firestore.production.rules denies client
reads/writes; backend Admin SDK access is separate. Confirm this policy remains
deployed before live use. config/firestore.rules is permissive and intended only for an emulator;
do not deploy it to production. This change does not deploy database rules.

Verification tests use mocked sessions and an in-memory database. A live LINE
login plus one real submission is still needed after deployment to verify cloud
configuration and persistence. Tests must not write to production.
