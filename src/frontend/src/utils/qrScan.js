export const QR_SCAN_ERROR_CODES = Object.freeze({
  EMPTY: 'EMPTY_QR',
  INVALID_URL: 'INVALID_QR_URL',
});

export class QrScanInputError extends Error {
  constructor(code) {
    super(code);
    this.name = 'QrScanInputError';
    this.code = code;
  }
}

export function normalizeScannedUrl(value) {
  const candidate = typeof value === 'string' ? value.trim() : '';
  if (!candidate) {
    throw new QrScanInputError(QR_SCAN_ERROR_CODES.EMPTY);
  }

  try {
    const url = new URL(candidate);
    if ((url.protocol !== 'http:' && url.protocol !== 'https:') || !url.hostname ||
        url.username || url.password || candidate.length > 2048 || /\s/u.test(candidate) ||
        !/^https?:\/\//iu.test(candidate)) {
      throw new QrScanInputError(QR_SCAN_ERROR_CODES.INVALID_URL);
    }
  } catch (error) {
    if (error instanceof QrScanInputError) throw error;
    throw new QrScanInputError(QR_SCAN_ERROR_CODES.INVALID_URL);
  }

  return candidate;
}

export async function readQrUrl(scan, { signal, timeoutMs = 60000 } = {}) {
  if (signal?.aborted) throw new QrScanInputError('QR_SCAN_CANCELLED');
  let timer, cancel;
  try {
    const cancelled = new Promise((_, reject) => {
      cancel = () => reject(new QrScanInputError('QR_SCAN_CANCELLED'));
      signal?.addEventListener('abort', cancel, { once: true });
      timer = setTimeout(() => reject(new QrScanInputError('QR_SCAN_TIMEOUT')), timeoutMs);
    });
    return normalizeScannedUrl(await Promise.race([Promise.resolve().then(scan), cancelled]));
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}

export function isQrScanCancelled(error) {
  const errorText = `${error?.code || ''} ${error?.message || ''}`.toLowerCase();
  return errorText.includes('cancel');
}

export function getQrScanError(error) {
  const imageErrors = {
    QR_IMAGE_TYPE: ['เลือกรูป JPG, PNG หรือ WebP', 'ไฟล์รูปแบบนี้ยังไม่รองรับ กรุณาเลือกรูปอื่น'],
    QR_IMAGE_SIZE: ['รูปมีขนาดไม่เหมาะสม', 'กรุณาเลือกรูปที่มีขนาดไม่เกิน 10 MB'],
    QR_IMAGE_INVALID: ['อ่านภาพนี้ไม่ได้', 'กรุณาเลือกรูป JPG, PNG หรือ WebP ที่เปิดดูได้ตามปกติ'],
    QR_IMAGE_NOT_FOUND: ['ไม่สามารถอ่าน QR Code จากภาพได้', 'ไม่พบ QR Code หรือภาพไม่ชัดเจน กรุณาเลือกรูปอื่น'],
    QR_IMAGE_TIMEOUT: ['อ่าน QR Code จากภาพนานเกินไป', 'กรุณาเลือกรูปที่เล็กลงหรือชัดเจนขึ้น แล้วลองอีกครั้ง'],
    QR_SCAN_TIMEOUT: ['สแกน QR Code นานเกินไป', 'กรุณาลองสแกนอีกครั้ง หรือแนบภาพ QR Code'],
  };
  if (imageErrors[error?.code]) {
    const [title, message] = imageErrors[error.code];
    return { icon: 'warning', title, message };
  }
  if (error instanceof QrScanInputError) {
    return error.code === QR_SCAN_ERROR_CODES.EMPTY
      ? {
          icon: 'warning',
          title: 'ไม่พบข้อมูลใน QR Code',
          message: 'กรุณาลองสแกน QR Code อีกครั้ง',
        }
      : {
          icon: 'warning',
          title: 'QR Code นี้ไม่ใช่ลิงก์',
          message: 'กรุณาสแกน QR Code ที่มี URL ขึ้นต้นด้วย http:// หรือ https://',
        };
  }

  const errorText = `${error?.code || ''} ${error?.message || ''}`.toLowerCase();
  if (errorText.includes('permission') || errorText.includes('denied') || errorText.includes('notallowed')) {
    return {
      icon: 'error',
      title: 'ไม่สามารถเปิดกล้องได้',
      message: 'กรุณาอนุญาตการใช้กล้อง แล้วลองสแกนอีกครั้ง',
    };
  }

  if (errorText.includes('scan_not_supported') || errorText.includes('not supported') || errorText.includes('unsupported')) {
    return {
      icon: 'info',
      title: 'อุปกรณ์นี้ไม่รองรับการสแกน',
      message: 'กรุณาเปิด GunGong ผ่านแอป LINE เวอร์ชันล่าสุด',
    };
  }

  if (errorText.includes('liff not available') || errorText.includes('not_in_line')) {
    return {
      icon: 'info',
      title: 'เปิดผ่านแอป LINE เพื่อสแกน',
      message: 'คุณยังสามารถวาง URL ในช่องด้านบนเพื่อตรวจสอบได้',
    };
  }

  return {
    icon: 'error',
    title: 'สแกน QR Code ไม่สำเร็จ',
    message: 'กรุณาลองใหม่อีกครั้ง หรือวาง URL ด้วยตนเอง',
  };
}
