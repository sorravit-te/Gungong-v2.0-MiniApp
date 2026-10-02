import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { decodeQrPixels } from '../src/shared/qr/qrImagePixels.js';
import { MAX_QR_IMAGE_BYTES, readQrImageUrl, validateQrImage } from '../src/shared/qr/qrImage.js';
import { getQrScanError, normalizeScannedUrl, readQrUrl } from '../src/shared/qr/qrScan.js';
import { qrPixels, qrUrl } from './fixtures/qrMatrix.js';

const file = { type: 'image/png', size: 100 };
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');


test('real QR pixel decoder reads normal, rotated and inverted QR rasters', () => {
  for (const options of [{}, { rotated: true }, { inverted: true }]) {
    const { data, width, height } = qrPixels(options);
    assert.equal(decodeQrPixels(data, width, height), qrUrl);
  }
  assert.equal(decodeQrPixels(new Uint8ClampedArray(100 * 100 * 4).fill(255), 100, 100), null);
  assert.throws(() => decodeQrPixels(new Uint8ClampedArray(4), 2000, 3000), /QR_IMAGE_INVALID/u);
});

test('attachments accept supported raster formats and reject empty/oversized/unsupported files', () => {
  for (const type of ['image/png', 'image/jpeg', 'image/webp']) validateQrImage({ ...file, type });
  for (const type of ['image/svg+xml', 'image/heic', 'text/plain']) {
    assert.throws(() => validateQrImage({ ...file, type }), /QR_IMAGE_TYPE/u);
  }
  for (const size of [0, MAX_QR_IMAGE_BYTES + 1]) {
    assert.throws(() => validateQrImage({ ...file, size }), /QR_IMAGE_SIZE/u);
  }
});

// Browser resource mocks exercise async lifetime; real decoding is tested above.
function browser(t, outcome = qrUrl, { corrupt = false, stalled = false } = {}) {
  const state = { revoked: 0, terminated: 0, canvas: null };
  const originals = { Image: globalThis.Image, Worker: globalThis.Worker, document: globalThis.document,
    create: URL.createObjectURL, revoke: URL.revokeObjectURL };
  URL.createObjectURL = () => 'blob:test-only';
  URL.revokeObjectURL = () => state.revoked++;
  globalThis.Image = class {
    naturalWidth = 100; naturalHeight = 100;
    set src(value) {
      if (value) queueMicrotask(() => corrupt ? this.onerror?.() : this.onload?.());
    }
  };
  globalThis.document = { createElement: () => {
    state.canvas = { getContext: () => ({ fillRect() {}, drawImage() {},
      getImageData: () => ({ data: new Uint8ClampedArray(40000) }) }) };
    return state.canvas;
  } };
  globalThis.Worker = class {
    postMessage() { if (!stalled) queueMicrotask(() => this.onmessage?.({ data: { value: outcome } })); }
    terminate() { state.terminated++; }
  };
  t.after(() => {
    globalThis.Image = originals.Image; globalThis.Worker = originals.Worker;
    globalThis.document = originals.document;
    URL.createObjectURL = originals.create; URL.revokeObjectURL = originals.revoke;
  });
  return state;
}

test('successful image reads fill a validated URL and release worker, pixels and object URL', async t => {
  const state = browser(t);
  assert.equal(await readQrImageUrl(file), qrUrl);
  assert.equal(state.revoked, 1); assert.equal(state.terminated, 1);
  assert.equal(state.canvas.width, 0); assert.equal(state.canvas.height, 0);
});

test('images without QR provide a friendly warning and release resources', async t => {
  const state = browser(t, null);
  const error = await readQrImageUrl(file).catch(error => error);
  assert.equal(error.code, 'QR_IMAGE_NOT_FOUND');
  assert.match(getQrScanError(error).title, /ไม่สามารถอ่าน QR Code จากภาพได้/u);
  assert.equal(state.revoked, 1); assert.equal(state.terminated, 1);
});

test('QR containing non-URL data cannot become a scanner/report URL', async t => {
  browser(t, 'payment-only-secret');
  await assert.rejects(readQrImageUrl(file), /INVALID_QR_URL/u);
  for (const value of ['javascript:alert(1)', 'https://a:b@example.com', 'https://example.com/has space']) {
    assert.throws(() => normalizeScannedUrl(value));
  }
});

test('corrupt images fail without keeping their object URL', async t => {
  const state = browser(t, null, { corrupt: true });
  await assert.rejects(readQrImageUrl(file), /QR_IMAGE_INVALID/u);
  assert.equal(state.revoked, 1);
});

test('image timeout terminates a stalled decoder', async t => {
  const state = browser(t, null, { stalled: true });
  await assert.rejects(readQrImageUrl(file, { timeoutMs: 10 }), /QR_IMAGE_TIMEOUT/u);
  assert.equal(state.revoked, 1); assert.equal(state.terminated, 1);
});

test('aborting an image read cancels stale output and releases all resources', async t => {
  const state = browser(t, null, { stalled: true });
  const controller = new AbortController();
  const result = readQrImageUrl(file, { signal: controller.signal });
  await new Promise(resolve => setTimeout(resolve, 0));
  controller.abort();
  await assert.rejects(result, /QR_SCAN_CANCELLED/u);
  assert.equal(state.revoked, 1); assert.equal(state.terminated, 1);
});

test('camera cancellation/deadline stop waiting, without requesting the scanned URL', async () => {
  const pending = () => new Promise(() => {});
  await assert.rejects(readQrUrl(pending, { timeoutMs: 10 }), /QR_SCAN_TIMEOUT/u);
  const controller = new AbortController();
  const result = readQrUrl(pending, { signal: controller.signal });
  controller.abort();
  await assert.rejects(result, /QR_SCAN_CANCELLED/u);
});

test('Scanner and link reports share QR controls, reset same-file input and cancel stale reads', () => {
  const scanner = read('../src/features/scanner/scanner.jsx'), report = read('../src/features/report/report.jsx');
  const actions = read('../src/shared/qr/QrInputActions.jsx');
  assert.match(scanner, /<QrInputActions/u); assert.match(report, /draft.kind === 'link' && <QrInputActions/u);
  assert.match(scanner, /onRead=\{url => handleInputChange\('link', url\)\}/u);
  assert.match(report, /onRead=\{url => change\('content', url\)\}/u);
  assert.match(actions, /event.target.value = ''/u);
  assert.match(actions, /activeRequest.current\?\.abort\(\), \[resetKey\]/u);
  assert.match(actions, /request.signal.aborted/u);
  assert.doesNotMatch(actions, /submitContentReport|checkLink|fetch\(/u);
});

test('Community centers its heading and has a plus inside its single composer button', () => {
  const social = read('../src/features/community/social.jsx'), css = read('../src/features/community/social.css');
  assert.match(social, /<button className="community-compose-trigger"[\s\S]*?<span className="community-compose-plus" aria-hidden="true">\+<\/span>[\s\S]*?<\/button>/u);
  assert.match(css, /#social-page \.scanner-header \{[^}]*justify-content: center;/u);
});

test('all Sidebar items use one uniform group, including Scanner', () => {
  const sidebar = read('../src/shared/layout/Sidebar.jsx'), css = read('../src/shared/layout/sidebar.css');
  assert.match(sidebar, /title: 'Primary', items: PRIMARY_NAV_ITEMS/u);
  assert.doesNotMatch(sidebar, /title: 'Main'|title: 'Tools'|title: 'Management'|PRIMARY_NAV_ITEMS\.slice/u);
  assert.match(css, /\.menu-group-items \{[^}]*gap: 2px;/u);
});
