import test from 'node:test';
import assert from 'node:assert/strict';

import { parseApiResponse } from '../src/utils/parseApiResponse.js';

const jsonResponse = (status, data) => new Response(JSON.stringify(data), {
  status,
  headers: { 'content-type': 'application/json' },
});

test('returns parsed data for a successful JSON response', async () => {
  const data = await parseApiResponse(jsonResponse(200, { success: true }));
  assert.deepEqual(data, { success: true });
});

test('uses detail from a JSON 400 response', async () => {
  await assert.rejects(
    () => parseApiResponse(jsonResponse(400, { detail: 'Invalid synthetic ID' })),
    { message: 'Invalid synthetic ID' },
  );
});

test('uses error from a JSON 500 response', async () => {
  await assert.rejects(
    () => parseApiResponse(jsonResponse(500, { error: 'Verification unavailable' })),
    { message: 'Verification unavailable' },
  );
});

test('reports an empty 502 response without attempting JSON parsing', async () => {
  await assert.rejects(
    () => parseApiResponse(new Response('', { status: 502 })),
    { message: 'เซิร์ฟเวอร์ไม่ส่งข้อมูลตอบกลับ (HTTP 502)' },
  );
});

test('reports non-JSON 502 without exposing the response body', async () => {
  const originalWarn = console.warn;
  let diagnostic;
  console.warn = (message, metadata) => {
    diagnostic = { message, metadata };
  };

  try {
    await assert.rejects(
      () => parseApiResponse(new Response('<html>private gateway error</html>', {
        status: 502,
        headers: { 'content-type': 'text/html; charset=utf-8' },
      })),
      (error) => {
        assert.equal(error.message, 'เซิร์ฟเวอร์ตอบกลับในรูปแบบไม่ถูกต้อง (HTTP 502)');
        assert.equal(error.message.includes('<html>'), false);
        return true;
      },
    );
  } finally {
    console.warn = originalWarn;
  }

  assert.equal(diagnostic.message, 'API returned a non-JSON response');
  assert.equal(diagnostic.metadata.status, 502);
  assert.equal(Object.hasOwn(diagnostic.metadata, 'body'), false);
});
