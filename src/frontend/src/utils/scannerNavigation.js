export const SCANNER_SUBMENU_ITEMS = Object.freeze([
  Object.freeze({ id: 'check-content', label: 'Check Content' }),
  Object.freeze({ id: 'check-personal', label: 'Check Personal' }),
]);

export const SCANNER_ROUTE_IDS = Object.freeze([
  ...SCANNER_SUBMENU_ITEMS.map(({ id }) => id),
  'scan-image',
  'scan-qr',
]);
