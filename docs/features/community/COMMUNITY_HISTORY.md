# Shared Community and private History

Community uses `community_posts`, not scan history. Reading the feed is public;
posting requires a verified LINE access token or Firebase ID token. The server
derives the author identity/name, limits posts to 2,000 characters and five
requests/minute per IP, and uses an identity-scoped request UUID to avoid duplicate
posts after lost responses. No automatic repost/retry, likes or
comments are implemented. React renders posts as text (no HTML or automatic
navigation to untrusted URLs). Public posts must not contain passwords/OTP or
private information. The feed refreshes on focus/visibility and every 30 seconds
while visible; this is bounded polling, not instant real-time push. Firestore
reads/writes use explicit RPC deadlines and no automatic RPC retries.

The composer opens a native modal dialog (full-screen on mobile). One JPEG/PNG/
WebP attachment is supported per post, including image-only posts. The browser
resizes/compresses originals up to 10 MB to at most 128 KiB. The authenticated API
caps JSON bodies at 256 KiB even for streamed bodies, validates actual raster
content and dimensions, rejects SVG/animation, and re-encodes JPEG without EXIF/
GPS metadata. Bytes are stored atomically in the same Firestore post document;
UUID retries also compare the image hash. No separate upload can leave an orphan.
Feed reads project metadata only; images are lazy-loaded through an ID-bound,
public, immutable image endpoint. No Cloud Storage bucket, billing upgrade or new
paid service is enabled. This small-image approach is for the current free-tier
MVP, not unlimited photo hosting: existing Firestore storage/read and network
quotas still apply. Public posts/images have no automated moderation yet.

History list/detail and feedback require verified identity and enforce ownership
on the server. A browser-supplied `user_id` is never proof of ownership. Personal
scan requests bind History to verified identity; anonymous scans remain possible
without personal History. The shared mock identity has been removed. LINE Login
channel `2008548759` must own the deployed LIFF app; tokens issued for another
channel are rejected. Google identities are separate from LINE identities: no
implicit account linking or migration of old mock/group-owned History occurs.
Bank/phone scan History uses the same verified-owner binding; blacklist analysis
itself is unchanged. This audit covers the application's active UI/webhook paths,
not all unused legacy v2 API implementations.

Signed URL bot events persist History before reply, including cache hits. Text
bot cache hits previously referenced an uninitialized `has_malicious_urls`,
silently skipping the History write. That variable is now initialized on both
paths; text events persist before reply and use the correct text/link type.
Saving does not depend on pressing the Flex card. Writes have a three-second RPC
budget; database failure cannot guarantee a saved entry. Existing records are
not rewritten. History refreshes when the user returns to the page and every 30
seconds while visible. Provider/detail evidence remains stored unchanged.
History UI reads skip the unused total-count query; API callers retain totals
by default. The UI has a 15-second overall read deadline (including session and
response body), one retry for transient network/502/503/504 failures, and refresh
on return to the page. Authentication/ownership failures are never retried or bypassed.

Live Firestore Rules already deny all direct client access (verified 2026-10-02),
including these two collections. No cloud Rules change was needed. The matching
policy is recorded in `config/firestore.production.rules`; never deploy the
emulator-only `config/firestore.rules` to Production. The API uses the existing
server credentials; all other collection rules remain unchanged.
This is not a full database security audit. No provider keys/tokens are logged,
and tokens are not cached in browser storage. Firebase tokens are signature,
issuer, expiry and audience verified; immediate revocation checks are not added.

The obsolete `render.yaml` is removed; Vercel's root Dockerfile is retained.
Historical migration/test notes referring to prior hosting are evidence, not
active dependencies. No old cloud service is disabled or deleted by this change.
