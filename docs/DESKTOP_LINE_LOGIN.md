# Desktop LINE login

Open https://gungong-vercel-preview.vercel.app/ in a desktop browser and choose
the LINE logo at the bottom-left. LIFF initializes once per page using the official LINE
SDK and existing Published LIFF ID `2008548759-KkM4Noxa`. Anonymous desktop browsing does
not force a redirect. The LINE client keeps its existing automatic authorization;
external browsers explicitly invoke `liff.login()` after initialization.

The redirect origin is the existing Production endpoint, never a browser-supplied
return URL. Only an allowlisted app section and bounded `historyId` are carried
through; OAuth parameters are not copied. After returning, LIFF initializes and
reads the current profile. Initialization/profile UI waits are bounded to eight
seconds with timer cleanup; the SDK does not expose cancellation, so a timed-out
initialization is not started again concurrently. Late initialization cannot
start a login redirect after the UI deadline. A failed SDK load may require
refreshing the page. Errors do not include raw tokens/provider responses.

LINE profile presentation takes the same priority as API session headers. Private
History and Community posting continue using the server-verified LINE token and
existing channel audience `2008548759`; no new identity, custom OAuth backend,
database migration, permissive Rules or account linking is introduced. History/
Community remount when the identity changes so another session cannot retain the
previous user's list. External logout clears LINE and the memory-only History cache;
the LINE client is not offered a misleading persistent logout. Google login, its
UI and frontend session fallback have been removed. Existing Firestore data and
server-side legacy authentication compatibility are not deleted. Analytics is deferred until SDK initialization and skipped while
OAuth/LIFF callback parameters remain in the URL.

No LINE Developers settings are automatically changed. The Published endpoint
must still be `https://gungong-vercel-preview.vercel.app/` and permit the existing
profile scope. Localhost and generated Preview origins are not configured LINE
OAuth callback endpoints; a local login button returns to Production, not local
development. Use the endpoint URL above on a computer if the MINI App launch URL
shows a mobile QR interstitial. LINE-only capabilities remain environment-specific;
desktop login does not claim every mobile sharing/camera API is available.

## Mobile central-link handoff

On the exact Production origin, external Android/iOS browsers are sent to the
Published `https://miniapp.line.me/2008548759-KkM4Noxa` permanent link before waiting
for LIFF initialization, preserving only approved section/history navigation. The
documented pre-init `getOS`/`isInClient` APIs detect the environment; external mobile
user-agent detection also works if the SDK failed to load. Desktop,
local development, generated Preview origins, LINE-client pages and OAuth/LIFF
callbacks (including `liff.*` parameters and OAuth fragments) are excluded. A
non-sensitive timestamp in sessionStorage prevents immediate fallback loops for
30 seconds, rather than suppressing all later visits in that tab. The old permanent
`attempted` marker is ignored. An in-memory guard covers StrictMode or disabled
storage. A visible "เปิดใน LINE" HTTPS anchor remains available on external mobile
central-link pages, allowing a user gesture to launch the app even during the
cooldown. No deprecated `line://` scheme or window-closing workaround is used.
The OS/browser can still require an explicit Open in LINE tap or keep the user
in LINE's landing page; automatic app launch cannot be guaranteed by web code.

## Community and History read cache

Successful API list responses are cached in memory for 30 seconds, with in-flight
request deduplication. Returning within that interval does not repeat the read.
Expired data stays visible during background refresh; the existing 30-second poll,
focus and visibility refresh remain. History is keyed by the LINE user ID and
cleared on logout/identity changes and successful scanner checks. A late response
cannot repopulate an invalidated cache. Unauthorized refreshes clear private data;
transient failures retain prior data with an error. Community is public and a
successful post updates its first-page cache. No tokens, private History or drafts
are persisted in browser storage. Cached list data never replaces selected-record
detail reads or triggers URL/AI rescans.

Acceptance requiring the owner: complete LINE login in a desktop browser; verify
the same account name and private History as mobile; check another account cannot
read that History; logout and verify the list clears; confirm mobile Mini App/QR
input-only flow still works. Automated mocks do not prove a real account login.

Sources: [LINE MINI App external browsers](https://developers.line.biz/en/docs/line-mini-app/develop/external-browser/),
[LIFF login API](https://developers.line.biz/en/reference/liff/#login), and
[LINE Developers Thailand desktop demonstration](https://youtu.be/PP6D64pRrqk?t=350).
See also [permanent links](https://developers.line.biz/en/docs/line-mini-app/develop/permanent-links/)
and [documented pre-init APIs](https://developers.line.biz/en/reference/liff/#initializing-liff-app)
and [OS/browser launch limitations](https://developers.line.biz/en/tips/2026/05/07/line-launch-issue/).
