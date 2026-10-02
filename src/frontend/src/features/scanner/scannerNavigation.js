export const SCANNER_FEATURE_ITEMS = Object.freeze([
  Object.freeze({ id: 'check-link', label: 'ตรวจสอบลิงก์ / QR Code' }),
  Object.freeze({ id: 'check-sms', label: 'ตรวจสอบข้อความ' }),
]);

export const SCANNER_ROUTE_IDS = Object.freeze([
  ...SCANNER_FEATURE_ITEMS.map(({ id }) => id),
  'check-content',
  'scan-image',
  'scan-qr',
]);

// Keep old content/QR entry links working without exposing the paused personal checks.
export const resolveScannerSubPage = (route) => {
  if (route === 'check-content' || route === 'scan-qr') return 'check-link';
  return SCANNER_FEATURE_ITEMS.some(({ id }) => id === route) ? route : null;
};
