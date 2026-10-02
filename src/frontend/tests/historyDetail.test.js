import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createHistoryDetailController } from '../src/features/history/utils/historyDetail.js';

globalThis.window = {
  location: { hostname: 'localhost', protocol: 'http:', origin: 'http://localhost:5173' },
  liff: { isLoggedIn: () => true, getAccessToken: () => 'test-only-token' },
};
const { getHistoryById } = await import('../src/shared/api/script.js');

const aiReason = 'เป็นหน้าข้อมูลทั่วไป ไม่พบสัญญาณการหลอกลวงจากเนื้อหาที่ตรวจสอบ';
function record(overrides = {}) {
  return {
    id: 'history-one', type: 'link', message_text: 'https://unknown.test/full-path',
    classification: 'SAFE_NORMAL', is_safe: true, is_fraud: false,
    reason: 'ไม่พบสัญญาณอันตรายจากแหล่งข้อมูลที่ตรวจสอบ',
    url_check_result: {
      verification_verdict: 'NO_THREAT_FOUND', verification_complete: true,
      checks: { gemini: { status: 'clean', complete: true, evidence_sufficient: true, reason_th: aiReason } },
    }, ...overrides,
  };
}
function listItem(detail = record()) {
  return { ...detail, message_text: 'https://unknown.test/...', url_check_result: {
    verification_verdict: detail.url_check_result.verification_verdict,
    verification_complete: detail.url_check_result.verification_complete,
  } };
}
function popup() {
  return {
    calls: [], loadingCalls: 0, current: null,
    fire(options) {
      this.current?.didDestroy?.();
      this.current = options;
      this.calls.push(options);
      options.didOpen?.();
      return Promise.resolve({});
    },
    showLoading() { this.loadingCalls++; },
    close() { this.current?.willClose?.(); this.current?.didDestroy?.(); this.current = null; },
  };
}
function controller(getDetail, options = {}) {
  const swal = popup();
  return { swal, flow: createHistoryDetailController({ getDetail, swal, typeName: type => type, ...options }) };
}
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

test('History component wires the selected-record reader and disposes it on unmount', () => {
  const source = readFileSync(new URL('../src/features/history/history.jsx', import.meta.url), 'utf8');
  assert.match(source, /getDetail: getHistoryById/u);
  assert.match(source, /detailController\.current\.open\(item\)/u);
  assert.match(source, /detailController\.current\?\.dispose\(\)/u);
});

test('fresh and cache-hit URL history load only the clicked detail and preserve Thai AI wording', async () => {
  for (const cached of [false, true]) {
    const detail = record({ cached });
    const calls = [];
    const { flow, swal } = controller(async (id, options) => {
      calls.push({ id, signal: options.signal }); return detail;
    });
    await flow.open(listItem(detail));
    assert.equal(calls.length, 1);
    assert.equal(calls[0].id, detail.id);
    assert.equal(swal.loadingCalls, 1);
    assert.match(swal.calls[1].html, new RegExp(aiReason, 'u'));
    assert.match(swal.calls[1].html, /full-path/u);
    assert.equal(swal.calls[1].icon, 'success');
    assert.doesNotMatch(swal.calls[1].html, /ความมั่นใจ/u);
  }
});

test('QR uses stored detail while text/bank/phone preserve the existing no-fetch popup', async () => {
  let reads = 0;
  const { flow, swal } = controller(async id => { reads++; return record({ id, type: 'qr' }); });
  await flow.open(listItem(record({ type: 'qr' })));
  assert.equal(reads, 1);
  for (const type of ['text', 'sms', 'bank', 'phone']) {
    await flow.open({ id: type, type, message_text: 'legacy', is_safe: true, confidence_score: 90 });
    assert.equal(swal.current.icon, 'success');
    assert.match(swal.current.html, /ความมั่นใจ/u);
  }
  assert.equal(reads, 1);
});

test('non-URL History titles are plain text and retain their result icons', async () => {
  const { flow, swal } = controller(async () => { throw new Error('unexpected detail read'); });
  await flow.open({ id: 'safe-text', type: 'text', is_safe: true });
  assert.equal(swal.current.title, 'ปลอดภัย');
  assert.equal(swal.current.icon, 'success');
  await flow.open({ id: 'risk-text', type: 'text', is_safe: false, is_fraud: true });
  assert.equal(swal.current.title, 'อันตราย!');
  assert.equal(swal.current.icon, 'warning');
});

test('History keeps incomplete verdict distinct despite a stored clean AI assessment', async () => {
  const detail = record();
  detail.url_check_result.verification_verdict = 'INCOMPLETE';
  detail.url_check_result.verification_complete = false;
  const { flow, swal } = controller(async () => detail);
  await flow.open(listItem(detail));
  assert.equal(swal.current.icon, 'info');
  assert.equal(swal.current.title, 'ตรวจสอบได้ไม่ครบ');
  assert.equal(swal.current.html.includes(aiReason), false);
});

test('404, 500 and network failure replace the loader without presenting list data as a full result', async () => {
  for (const status of [404, 500, undefined]) {
    const { flow, swal } = controller(async () => { throw Object.assign(new Error('private diagnostic'), { status }); });
    await flow.open(listItem());
    assert.equal(swal.calls.length, 2);
    assert.equal(swal.current.icon, 'error');
    assert.equal(swal.current.title, 'ไม่สามารถโหลดรายละเอียดประวัติได้');
    assert.equal(JSON.stringify(swal.current).includes('private diagnostic'), false);
    if (status === 404) assert.match(swal.current.text, /ไม่พบรายการ/u);
  }
});

test('empty, malformed or mismatched records do not display another record or stale list explanation', async () => {
  for (const detail of [null, [], {}, record({ id: 'other' }), record({ type: 'text' }), record({ message_text: null })]) {
    const { flow, swal } = controller(async () => detail);
    await flow.open(listItem());
    assert.equal(swal.current.icon, 'error');
    assert.equal(swal.current.html, undefined);
  }
});

test('missing selected ID never sends a detail request', async () => {
  let calls = 0;
  const { flow, swal } = controller(async () => { calls++; });
  await flow.open({ ...listItem(), id: undefined });
  assert.equal(calls, 0);
  assert.equal(swal.current.icon, 'error');
});

test('detail deadline aborts stalled reads and settles the loading popup', async () => {
  let signal;
  const { flow, swal } = controller((_id, options) => {
    signal = options.signal; return new Promise(() => {});
  }, { timeoutMs: 5 });
  await flow.open(listItem());
  assert.equal(signal.aborted, true);
  assert.equal(swal.current.icon, 'error');
  assert.match(swal.current.text, /นานเกินกำหนด/u);
});

test('successful detail clears its timer rather than later aborting or replacing the popup', async () => {
  let signal;
  const { flow, swal } = controller(async (_id, options) => {
    signal = options.signal; return record();
  }, { timeoutMs: 5 });
  await flow.open(listItem());
  await new Promise(resolve => setTimeout(resolve, 15));
  assert.equal(signal.aborted, false);
  assert.equal(swal.calls.length, 2);
});

test('closing the loader cancels the read and never reopens a late result', async () => {
  const pending = deferred();
  let signal;
  const { flow, swal } = controller((_id, options) => { signal = options.signal; return pending.promise; });
  const opening = flow.open(listItem());
  swal.close();
  await opening;
  pending.resolve(record());
  await Promise.resolve();
  assert.equal(signal.aborted, true);
  assert.equal(swal.calls.length, 1);
});

test('unmount cancels owned work, closes loader and rejects further popup activity', async () => {
  const pending = deferred();
  const { flow, swal } = controller(() => pending.promise);
  const opening = flow.open(listItem());
  flow.dispose();
  await opening;
  pending.resolve(record());
  await flow.open(listItem());
  assert.equal(swal.current, null);
  assert.equal(swal.calls.length, 1);
});

test('replacement by an unrelated popup cancels the read rather than overwriting that popup', async () => {
  const pending = deferred();
  const { flow, swal } = controller(() => pending.promise);
  const opening = flow.open(listItem());
  swal.fire({ title: 'Other action' });
  await opening;
  pending.resolve(record());
  await Promise.resolve();
  assert.equal(swal.current.title, 'Other action');
  assert.equal(swal.calls.length, 2);
});

test('a newer selection cancels the old read and only shows its own result', async () => {
  const pending = deferred();
  let firstSignal;
  const { flow, swal } = controller((id, options) => {
    if (id === 'history-one') { firstSignal = options.signal; return pending.promise; }
    return Promise.resolve(record({ id, message_text: 'https://second.test/' }));
  });
  const first = flow.open(listItem());
  await flow.open(listItem(record({ id: 'second' })));
  await first;
  pending.resolve(record());
  await Promise.resolve();
  assert.equal(firstSignal.aborted, true);
  assert.equal(swal.calls.length, 3);
  assert.match(swal.current.html, /second\.test/u);
});

test('stored page text and AI explanations remain HTML-escaped', async () => {
  const detail = record({ message_text: '<img src=x onerror=alert(1)>' });
  detail.url_check_result.checks.gemini.reason_th = 'ข้อมูล <script>alert(1)</script>';
  const { flow, swal } = controller(async () => detail);
  await flow.open(listItem());
  assert.doesNotMatch(swal.current.html, /<script>|<img/u);
  assert.match(swal.current.html, /&lt;script&gt;/u);
});

test('actual detail transport is one encoded GET with abort signal and no verifier/provider calls', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  const detail = record({ id: 'selected/id' });
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify(detail), { status: 200 });
  };
  try {
    const { flow, swal } = controller(getHistoryById);
    await flow.open(listItem(detail));
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, 'http://localhost:8000/history/selected%2Fid');
    assert.equal(calls[0].options.method, undefined);
    assert.ok(calls[0].options.signal instanceof AbortSignal);
    assert.equal(swal.current.icon, 'success');
  } finally { globalThis.fetch = originalFetch; }
});

test('HTTP errors and malformed JSON from actual detail transport settle as friendly errors', async () => {
  const originalFetch = globalThis.fetch;
  try {
    for (const response of [new Response('{}', { status: 404 }), new Response('', { status: 500 }), new Response('not json', { status: 200 })]) {
      globalThis.fetch = async () => response;
      const { flow, swal } = controller(getHistoryById);
      await flow.open(listItem());
      assert.equal(swal.current.icon, 'error');
    }
  } finally { globalThis.fetch = originalFetch; }
});
