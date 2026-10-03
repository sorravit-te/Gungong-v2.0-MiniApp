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
} = await import('../src/shared/api/script.js');
const { getFraudResultPresentation, getHistoryResultPresentation } = await import('../src/shared/results/fraudResultPresentation.js');

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
  assert.equal(incomplete.icon, 'info');
});

test('no-threat wording does not claim that a URL is absolutely safe', () => {
  const result = getFraudResultPresentation({ verification_verdict: 'NO_THREAT_FOUND' });
  assert.equal(result.status, 'ไม่พบสัญญาณอันตรายจากการตรวจสอบ');
  assert.equal(result.status.includes('ปลอดภัย'), false);
});

const amtsoReason = 'หน้าเว็บนี้เป็นหน้าทดสอบมาตรฐานของ AMTSO (Anti-Malware Testing Standards Organization) ซึ่งใช้สำหรับตรวจสอบว่าซอฟต์แวร์ป้องกันมัลแวร์สามารถตรวจจับหน้าฟิชชิ่งได้หรือไม่ ไม่ใช่หน้าเว็บฟิชชิ่งหรือหลอกลวงจริง';
const cleanGemini = {
  status: 'clean', complete: true, evidence_sufficient: true, reason_th: amtsoReason,
};

test('fresh and cached URL results preserve the specific AI explanation alongside honest status', () => {
  for (const cached of [false, true]) {
    const result = getFraudResultPresentation({
      cached, verification_verdict: 'NO_THREAT_FOUND',
      reason_th: 'ไม่พบสัญญาณอันตรายจากแหล่งข้อมูลที่ตรวจสอบ',
      checks: { gemini: cleanGemini },
    });
    assert.equal(result.analysisReason, amtsoReason);
    assert.equal(result.status, 'ไม่พบสัญญาณอันตรายจากการตรวจสอบ');
    assert.equal(result.showConfidence, false);
  }
});

test('nested URL check metadata also supplies the completed AI explanation', () => {
  const result = getFraudResultPresentation({
    verification_verdict: 'NO_THREAT_FOUND', url_check: { checks: { gemini: cleanGemini } },
  });
  assert.equal(result.analysisReason, amtsoReason);
});

test('clean AI explanations cannot contradict danger, incomplete, or invalid aggregate verdicts', () => {
  for (const verdict of ['MALICIOUS', 'SUSPICIOUS', 'INCOMPLETE', 'INVALID']) {
    const result = getFraudResultPresentation({
      verification_verdict: verdict, checks: { gemini: cleanGemini },
    });
    assert.equal(result.analysisReason, '');
    assert.equal(result.isSafe, false);
  }
});

test('missing, insufficient, unfinished, malformed, empty, and duplicate explanations are omitted', () => {
  for (const gemini of [
    undefined, { ...cleanGemini, complete: false },
    { ...cleanGemini, evidence_sufficient: false },
    { ...cleanGemini, status: 'uncertain' },
    { ...cleanGemini, reason_th: 123 }, { ...cleanGemini, reason_th: '  ' },
  ]) {
    assert.equal(getFraudResultPresentation({
      verification_verdict: 'NO_THREAT_FOUND', checks: { gemini },
    }).analysisReason, '');
  }
  assert.equal(getFraudResultPresentation({
    verification_verdict: 'NO_THREAT_FOUND', reason_th: ` ${amtsoReason} `,
    checks: { gemini: cleanGemini },
  }).analysisReason, '');
});

test('completed AI danger explanations are retained without changing the aggregate status', () => {
  for (const [verdict, status] of [['SUSPICIOUS', 'suspicious'], ['MALICIOUS', 'malicious']]) {
    const result = getFraudResultPresentation({
      verification_verdict: verdict,
      checks: { gemini: { status, complete: true, reason_th: 'พบสัญญาณหลอกขอรหัส OTP' } },
    });
    assert.equal(result.analysisReason, 'พบสัญญาณหลอกขอรหัส OTP');
    assert.equal(result.status, 'มีความเสี่ยง');
  }
});

test('legacy text results preserve reasoning but no longer display confidence', () => {
  const result = getFraudResultPresentation({
    is_safe: true, reason_th: 'ข้อความทั่วไป', checks: { gemini: cleanGemini },
  });
  assert.equal(result.analysisReason, '');
  assert.equal(result.showConfidence, false);
  assert.equal(result.explanation, '');
});

test('every URL verdict has a Thai explanation even without an AI result', () => {
  for (const verdict of ['NO_THREAT_FOUND', 'SUSPICIOUS', 'MALICIOUS', 'INCOMPLETE', 'INVALID', 'UNKNOWN']) {
    const result = getFraudResultPresentation({ verification_verdict: verdict });
    assert.match(result.explanation, /[ก-๙]/u);
    assert.equal(result.explanationLabel, 'คำอธิบายการตรวจสอบ');
    assert.equal(result.analysisReason, '');
  }
});

test('trusted fast-path explains actual core evidence without pretending to use AI', () => {
  const result = getFraudResultPresentation({
    verification_verdict: 'NO_THREAT_FOUND',
    checks: {
      route: { status: 'FAST_SAFE' }, redirect: { status: 'clean', complete: true },
      content: { status: 'clean', complete: true, evidence_sufficient: true, content_truncated: true },
      local_reputation: { status: 'not_listed', complete: true },
      gemini: { status: 'skipped_not_needed', complete: null },
    },
  });
  assert.match(result.explanation, /ไม่จำเป็นต้องเรียก AI/u);
  assert.match(result.explanation, /ไม่ได้ตรวจเนื้อหาทั้งหน้า/u);
  assert.equal(result.explanationLabel, 'คำอธิบายการตรวจสอบ');
  assert.equal(result.analysisReason, '');
});

test('route name alone cannot claim completed trusted core evidence', () => {
  const result = getFraudResultPresentation({
    verification_verdict: 'NO_THREAT_FOUND', checks: { route: { status: 'FAST_SAFE' } },
  });
  assert.doesNotMatch(result.explanation, /ผ่านเกณฑ์โดเมนที่เชื่อถือ|ไม่จำเป็นต้องเรียก AI/u);
});

test('English AI explanations receive a Thai system fallback for fresh and cached results', () => {
  for (const cached of [false, true]) {
    const reason = 'The provided webpage is the official BBC homepage.';
    const result = getFraudResultPresentation({
      cached, verification_verdict: 'NO_THREAT_FOUND',
      checks: { gemini: { ...cleanGemini, reason_th: reason } },
    });
    assert.equal(result.analysisReason, '');
    assert.match(result.explanation, /[ก-๙]/u);
    assert.equal(result.explanation.includes(reason), false);
    assert.equal(result.explanationLabel, 'คำอธิบายการตรวจสอบ');
    assert.equal(result.isSafe, true);
  }
});

test('consistent Thai AI explanations are attributed to AI and preserved in full', () => {
  const result = getFraudResultPresentation({
    verification_verdict: 'NO_THREAT_FOUND', checks: { gemini: cleanGemini },
  });
  assert.equal(result.explanation, amtsoReason);
  assert.equal(result.explanationLabel, 'คำอธิบายการตรวจสอบ (AI)');
});

test('incomplete explanations identify only unfinished required stages and never use clean AI wording', () => {
  const result = getFraudResultPresentation({
    verification_verdict: 'INCOMPLETE',
    checks: {
      content: { status: 'timeout', complete: false, required: true },
      virustotal: { status: 'timeout', complete: false, required: false },
      gemini: cleanGemini,
    },
  });
  assert.match(result.explanation, /เนื้อหาหน้าเว็บ/u);
  assert.match(result.explanation, /ยังไม่สามารถยืนยันความปลอดภัย/u);
  assert.equal(result.explanation.includes(amtsoReason), false);
  assert.doesNotMatch(result.explanation, /VirusTotal/u);
  assert.equal(result.isSafe, false);
  assert.equal(result.isRisk, false);
  assert.match(result.explanation, /ไม่ได้หมายความว่าพบอันตราย/u);
});

test('single-engine and inherited warnings disclose their evidence limits', () => {
  for (const checks of [
    { virustotal: { status: 'suspicious', reason: 'single_engine_detection' } },
    { risk_history: { status: 'suspicious', reason: 'recent_detection_requires_confirmation' } },
  ]) {
    const result = getFraudResultPresentation({ verification_verdict: 'SUSPICIOUS', checks });
    assert.equal(result.isRisk, true);
    assert.equal(result.isSafe, false);
    assert.match(result.explanation, /ไม่ใช่การยืนยันว่าเว็บไซต์อันตรายแน่นอน/u);
  }
});

test('history incomplete URL is neither dangerous nor safe and hides AI safety percentage', () => {
  const result = getHistoryResultPresentation({ type: 'link', classification: 'VERIFICATION_INCOMPLETE',
    is_safe: null, is_fraud: null, confidence_score: 90 });
  assert.equal(result.isIncomplete, true);
  assert.equal(result.isRisk, false);
  assert.equal(result.isSafe, false);
  assert.equal(result.showConfidence, false);
  assert.equal(result.icon, 'info');
});

test('history uses verdict metadata and hides confidence for text too', () => {
  const result = getHistoryResultPresentation({ type: 'link', is_safe: true,
    url_check_result: { verification_verdict: 'SUSPICIOUS' } });
  assert.equal(result.isRisk, true);
  assert.equal(result.isSafe, false);
  const text = getHistoryResultPresentation({ type: 'text', classification: 'SCAM_MALICIOUS', is_fraud: true });
  assert.equal(text.showConfidence, false);
});

test('nested URL metadata supplies a Thai explanation without altering text-only results', () => {
  const result = getFraudResultPresentation({
    url_check: { verification_verdict: 'NO_THREAT_FOUND', checks: { gemini: cleanGemini } },
  });
  assert.equal(result.explanation, amtsoReason);
  assert.equal(result.showConfidence, false);
});
