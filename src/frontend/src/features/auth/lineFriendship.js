export const LINE_OA_URL = 'https://line.me/R/ti/p/@357asclq';

function supportsFriendship(sdk) {
  try {
    // AuthProvider initializes LIFF. Never initialize again or await liff.ready
    // here: ready can stay pending after a failed initialization.
    return Boolean(sdk?.id && sdk.isInClient?.() && sdk.isLoggedIn?.() &&
      sdk.getContext?.()?.viewType === 'full' &&
      typeof sdk.requestFriendship === 'function');
  } catch {
    return false;
  }
}

async function readFriendship(sdk, timeoutMs) {
  if (typeof sdk.getFriendship !== 'function') return null;
  let timer;
  try {
    const status = await Promise.race([
      sdk.getFriendship(),
      new Promise(resolve => { timer = setTimeout(() => resolve(null), timeoutMs); }),
    ]);
    return typeof status?.friendFlag === 'boolean' ? status.friendFlag : null;
  } catch {
    // Missing profile consent or a network error is not proof of friendship.
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// One action per mounted button. No startup requests, storage, token logging,
// automatic login, or retries. A second tap cannot open a second subwindow.
export function createLineFriendshipAction({
  getSdk = () => globalThis.window?.liff,
  fallback,
  onResult = () => {},
  onBusy = () => {},
  statusTimeoutMs = 4000,
}) {
  let busy = false;
  return async function requestFriendship() {
    if (busy) return { mode: 'busy' };
    busy = true;
    try {
      onBusy(true);
      const sdk = getSdk();
      if (!supportsFriendship(sdk)) {
        await fallback({ reason: 'unsupported' });
        return { mode: 'fallback' };
      }

      try {
        // Invoke directly from the tap, before awaiting any network work.
        // Thailand uses the linked OA, not the Japan-only multiple-OA option.
        await sdk.requestFriendship();
      } catch {
        await fallback({ reason: 'failed' });
        return { mode: 'fallback' };
      }

      // A resolved request only means the window closed. False/unknown must
      // never trigger a success message or another add-friend navigation.
      const friendFlag = await readFriendship(sdk, statusTimeoutMs);
      const result = { mode: 'native', friendFlag };
      await onResult(result);
      return result;
    } finally {
      busy = false;
      onBusy(false);
    }
  };
}
