import assert from 'node:assert/strict';
import test from 'node:test';

import { SCANNER_SUBMENU_ITEMS } from '../src/utils/scannerNavigation.js';
import {
  getQrScanError,
  isQrScanCancelled,
  normalizeScannedUrl,
  readQrUrl,
} from '../src/utils/qrScan.js';

test('Scanner submenu exposes only Check Content and Check Personal', () => {
  assert.deepEqual(SCANNER_SUBMENU_ITEMS, [
    { id: 'check-content', label: 'Check Content' },
    { id: 'check-personal', label: 'Check Personal' },
  ]);
  assert.equal(SCANNER_SUBMENU_ITEMS.some(({ label }) => label === 'Scan Image'), false);
});

test('manual and QR-provided HTTP URLs use the same normalized input value', async () => {
  const manualUrl = normalizeScannedUrl('https://example.com/manual');
  let linkChecks = 0;
  const qrUrl = await readQrUrl(async () => '  https://example.com/from-qr  ');

  assert.equal(manualUrl, 'https://example.com/manual');
  assert.equal(qrUrl, 'https://example.com/from-qr');
  assert.equal(linkChecks, 0, 'reading a QR URL must not submit a link check');

  const checkLink = (url) => {
    linkChecks += 1;
    return url;
  };
  assert.equal(checkLink(qrUrl), qrUrl);
  assert.equal(linkChecks, 1);
});

test('non-URL and empty QR values are rejected without exposing raw errors', async () => {
  for (const value of ['payment reference only', '', undefined]) {
    await assert.rejects(() => readQrUrl(async () => value));
    const error = await readQrUrl(async () => value).catch((caught) => caught);
    const message = getQrScanError(error);
    assert.ok(message.title);
    assert.ok(message.message);
    if (value) assert.equal(message.message.includes(value), false);
  }
});

test('scanner cancellation is silent and operational errors are user-safe', () => {
  assert.equal(isQrScanCancelled({ code: 'USER_CANCEL' }), true);
  assert.equal(isQrScanCancelled(new Error('camera permission denied')), false);

  const permissionError = getQrScanError(new Error('camera permission denied by browser internals'));
  assert.equal(permissionError.title, 'ไม่สามารถเปิดกล้องได้');
  assert.equal(permissionError.message.includes('browser internals'), false);

  const unknownError = getQrScanError(new Error('sensitive SDK stack detail'));
  assert.equal(unknownError.title, 'สแกน QR Code ไม่สำเร็จ');
  assert.equal(unknownError.message.includes('sensitive SDK stack detail'), false);
});
