const httpStatus = (response) => `HTTP ${response.status}`;

const getErrorMessage = (data, response) => {
  if (typeof data?.detail === 'string' && data.detail.trim()) {
    return data.detail;
  }
  if (typeof data?.error === 'string' && data.error.trim()) {
    return data.error;
  }
  return `การเรียก API ไม่สำเร็จ (${httpStatus(response)})`;
};

export async function parseApiResponse(response) {
  const body = await response.text();

  if (!body.trim()) {
    throw new Error(`เซิร์ฟเวอร์ไม่ส่งข้อมูลตอบกลับ (${httpStatus(response)})`);
  }

  let data;
  try {
    data = JSON.parse(body);
  } catch {
    const contentType = (response.headers.get('content-type') || 'unknown').slice(0, 80);
    console.warn('API returned a non-JSON response', {
      status: response.status,
      contentType,
    });
    throw new Error(`เซิร์ฟเวอร์ตอบกลับในรูปแบบไม่ถูกต้อง (${httpStatus(response)})`);
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(data, response));
  }

  return data;
}
