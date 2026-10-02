import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

import { SCANNER_FEATURE_ITEMS, SCANNER_ROUTE_IDS, resolveScannerSubPage } from '../src/utils/scannerNavigation.js';
import {
  getQrScanError,
  isQrScanCancelled,
  normalizeScannedUrl,
  readQrUrl,
} from '../src/utils/qrScan.js';

test('Scanner uses the emerald card and mascots 01, 02 and 03 in the requested positions', () => {
  const source = readFileSync(new URL('../src/components/scanner.jsx', import.meta.url), 'utf8');
  assert.match(source, /className="scanner-intro-mascot" src="\/img\/mascot_01\.png"/u);
  assert.match(source, /openFeature\('check-link'\)[\s\S]*?src="\/img\/mascot_02\.png"/u);
  assert.match(source, /openFeature\('check-sms'\)[\s\S]*?src="\/img\/mascot_03\.png"/u);
  assert.match(source, /src=\{contentTab === 'link' \? '\/img\/mascot_02\.png' : '\/img\/mascot_03\.png'\}/u);
  const css = readFileSync(new URL('../src/styles/scanner.css', import.meta.url), 'utf8');
  assert.match(css, /url\('\/img\/emerald_card\.png'\)/u);
  assert.doesNotMatch(css, /silver_card\.png/u);
  assert.doesNotMatch(source, /scanner-intro-shield|scanner-intro-logo|scanner-feature-icon/u);
});

test('Scanner exposes direct link/QR and text checks, without personal checks', () => {
  assert.deepEqual(SCANNER_FEATURE_ITEMS, [
    { id: 'check-link', label: 'ตรวจสอบลิงก์ / QR Code' },
    { id: 'check-sms', label: 'ตรวจสอบข้อความ' },
  ]);
  assert.ok(SCANNER_ROUTE_IDS.includes('check-link'));
  assert.ok(SCANNER_ROUTE_IDS.includes('check-sms'));
  assert.equal(SCANNER_ROUTE_IDS.includes('check-personal'), false);
});

test('Scanner routes open the requested form and safely handle legacy entries', () => {
  assert.equal(resolveScannerSubPage('check-link'), 'check-link');
  assert.equal(resolveScannerSubPage('check-sms'), 'check-sms');
  assert.equal(resolveScannerSubPage('check-content'), 'check-link');
  assert.equal(resolveScannerSubPage('scan-qr'), 'check-link');
  for (const route of [undefined, 'scanner', 'check-personal', 'check-bank', 'check-phone', 'unknown']) {
    assert.equal(resolveScannerSubPage(route), null);
  }
});

test('Scanner remounts each visible page so entrance animations replay on return', () => {
  const source = readFileSync(new URL('../src/components/scanner.jsx', import.meta.url), 'utf8');
  assert.match(source, /<section id="check-content-page" key=\{currentSubPage\}>/u);
  assert.match(source, /<section id="scanner-page" key="scanner">/u);
});

test('Scanner landing inherits the same entrance animations as other main pages', () => {
  const source = readFileSync(new URL('../src/components/scanner.jsx', import.meta.url), 'utf8');
  const css = readFileSync(new URL('../src/styles/scanner.css', import.meta.url), 'utf8');
  const sharedCss = readFileSync(new URL('../src/styles/main.css', import.meta.url), 'utf8');
  assert.match(source, /className="section-content scanner-landing"/u);
  assert.match(sharedCss, /\.section-content \{\s*animation: pageSlideIn 0\.4s ease-out forwards;/u);
  assert.match(sharedCss, /\.animate-card \{[^}]*animation: cardSlideIn 0\.4s ease-out forwards;/u);
  assert.doesNotMatch(css, /animation:\s*none/u);
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
