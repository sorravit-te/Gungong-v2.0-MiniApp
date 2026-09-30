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
    if ((url.protocol !== 'http:' && url.protocol !== 'https:') || !url.hostname) {
      throw new QrScanInputError(QR_SCAN_ERROR_CODES.INVALID_URL);
    }
  } catch (error) {
    if (error instanceof QrScanInputError) throw error;
    throw new QrScanInputError(QR_SCAN_ERROR_CODES.INVALID_URL);
  }

  return candidate;
}

export async function readQrUrl(scan) {
  return normalizeScannedUrl(await scan());
}

export function isQrScanCancelled(error) {
  const errorText = `${error?.code || ''} ${error?.message || ''}`.toLowerCase();
  return errorText.includes('cancel');
}

export function getQrScanError(error) {
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
