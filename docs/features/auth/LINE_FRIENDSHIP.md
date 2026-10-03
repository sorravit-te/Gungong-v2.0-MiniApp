# LINE Official Account friendship

The existing top-right GunGong logo opens `liff.requestFriendship()` directly
after a user tap in an initialized, logged-in LINE client with a Full LIFF view.
This works with an unverified MINI App; verification is not required.
The method uses the channel's linked Official Account without arguments.
Do not pass `officialAccount.id`: the multiple-account feature is restricted
to MINI App channels providing their service in Japan.

After the native window closes, `liff.getFriendship()` checks the real status.
Only a boolean `friendFlag: true` shows the confirmed-friend notice. Cancellation,
blocked/not-added status, missing profile consent, and failed or timed-out status
reads never claim success or automatically navigate to the OA. Status reads have
a four-second UI deadline; the SDK does not provide cancellation for that read.
The action is locked until the native window and optional feedback close.

External browsers, unavailable/uninitialized SDKs, non-Full views, and native
request failures use the existing logo confirmation dialog. Its confirm button
opens the existing GunGong OA link; cancel does nothing. There are no startup
friendship requests, new scopes, stored friendship flags, automatic login,
backend changes, or automatic Console changes.

## Required Console settings (Thailand)

1. In the LINE MINI App channel, open **Web app settings** and set
   **Add friend option** to **On (normal)**.
2. Under **Basic settings > Linked LINE Official Account**, link GunGong OA
   (`@357asclq`). The OA must have Messaging API enabled and its Messaging API
   channel must belong to the same provider as the MINI App channel. The operator
   needs Admin access to the MINI App channel and Administrator access to the OA.
3. Ensure the app has the `profile` scope and the user has granted it for the
   friendship-status check. If this is a LIFF app on a LINE Login channel instead,
   link the OA to that LINE Login channel and set the LIFF view size to **Full**.
4. Make sure the settings are reflected on the internal channel used for testing
   (Developing or Published). Do not change the existing endpoint or LIFF ID to
   enable this feature.

## Manual verification after deployment

- Open GunGong inside LINE, tap the top-right logo, and confirm the native window
  shows GunGong OA. Test adding the OA, cancelling, and unblocking a blocked OA.
- As an existing friend, the native window may close immediately; the app should
  show the confirmed-friend notice rather than opening another browser.
- Tap repeatedly and confirm only one window opens.
- In a desktop browser, confirm the original logo dialog is retained. Cancel
  must not navigate; confirm opens the correct OA link.
- Simulate a rejected status check: do not show a success notice or redirect.

Automated tests use mocked LIFF responses. They do not prove live channel linking
or actual friendship changes; test those on a phone after deployment.

## Official references

- [LIFF requestFriendship](https://developers.line.biz/en/reference/liff/#request-friendship)
- [LIFF getFriendship](https://developers.line.biz/en/reference/liff/#get-friendship)
- [MINI App add friend option](https://developers.line.biz/en/docs/line-mini-app/service/add-friend-option/)
