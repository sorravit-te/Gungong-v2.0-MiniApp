import assert from 'node:assert/strict';
import test from 'node:test';

globalThis.window = {
  location: { protocol: 'http:', hostname: 'localhost', origin: 'http://localhost:5173' },
};
globalThis.localStorage = {
  getItem: () => 'U_TEST',
};

const {
  callFraudCheckApi,
  checkLink,
  checkSMS,
  getErrorMessage,
} = await import('../src/utils/script.js');
const { getFraudResultPresentation } = await import('../src/utils/fraudResultPresentation.js');

test('link verification aborts with a stable timeout error', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => {
      const error = new Error('aborted');
      error.name = 'AbortError';
      reject(error);
    });
  });

  try {
    await assert.rejects(
      () => callFraudCheckApi('https://example.com/', 'link', { timeoutMs: 10 }),
      { message: 'REQUEST_TIMEOUT' },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('link deadline also bounds a stalled LIFF profile lookup', async () => {
  const originalFetch = globalThis.fetch;
  let fetchCalled = false;
  globalThis.fetch = async () => {
    fetchCalled = true;
    return new Response('{}', { status: 200 });
  };

  try {
    await assert.rejects(
      () => callFraudCheckApi('https://example.com/', 'link', {
        timeoutMs: 10,
        getUserIdFn: () => new Promise(() => {}),
      }),
      { message: 'REQUEST_TIMEOUT' },
    );
    assert.equal(fetchCalled, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('request timeout timer is cleared after a successful response', async () => {
  const originalFetch = globalThis.fetch;
  const originalClearTimeout = globalThis.clearTimeout;
  let cleared = false;
  globalThis.fetch = async () => new Response(JSON.stringify({ verification_verdict: 'NO_THREAT_FOUND' }), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
  globalThis.clearTimeout = (timer) => {
    cleared = true;
    return originalClearTimeout(timer);
  };

  try {
    const result = await callFraudCheckApi('https://example.com/', 'link', { timeoutMs: 100 });
    assert.equal(result.verification_verdict, 'NO_THREAT_FOUND');
    assert.equal(cleared, true);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.clearTimeout = originalClearTimeout;
  }
});

test('backend 4xx/5xx and network failures settle instead of leaving the request pending', async () => {
  const originalFetch = globalThis.fetch;
  try {
    for (const status of [400, 503]) {
      globalThis.fetch = async () => new Response(JSON.stringify({ detail: `failure-${status}` }), {
        status,
        headers: { 'content-type': 'application/json' },
      });
      await assert.rejects(() => checkLink('https://example.com/'), { message: `failure-${status}` });
    }

    globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
    await assert.rejects(() => checkLink('https://example.com/'), /Failed to fetch/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('empty successful response is rejected as malformed', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response('', { status: 200 });
  try {
    await assert.rejects(() => checkLink('https://example.com/'), { message: 'INVALID_RESPONSE' });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('text flow remains backward compatible and sends sms metadata', async () => {
  const originalFetch = globalThis.fetch;
  let requestBody;
  globalThis.fetch = async (_url, options) => {
    requestBody = JSON.parse(options.body);
    return new Response(JSON.stringify({ category: 'SAFE_NORMAL', is_fraud: false }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    const result = await checkSMS('ข้อความทดสอบ');
    assert.equal(result.category, 'SAFE_NORMAL');
    assert.equal(requestBody.message_type, 'sms');
    assert.equal(requestBody.message, 'ข้อความทดสอบ');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('URL timeout and incomplete verdict use distinct honest wording', () => {
  const timeoutMessage = getErrorMessage(new Error('REQUEST_TIMEOUT'));
  assert.equal(timeoutMessage.message, 'การตรวจสอบลิงก์ใช้เวลานานเกินกำหนด กรุณาลองใหม่อีกครั้ง');

  const incomplete = getFraudResultPresentation({
    verification_verdict: 'INCOMPLETE',
    is_fraud: false,
    is_safe: false,
  });
  assert.equal(incomplete.status, 'ตรวจสอบได้ไม่ครบ');
  assert.equal(incomplete.isSafe, false);
  assert.equal(incomplete.icon, 'warning');
});

test('no-threat wording does not claim that a URL is absolutely safe', () => {
  const result = getFraudResultPresentation({ verification_verdict: 'NO_THREAT_FOUND' });
  assert.equal(result.status, 'ไม่พบสัญญาณอันตรายจากการตรวจสอบ');
  assert.equal(result.status.includes('ปลอดภัย'), false);
});
