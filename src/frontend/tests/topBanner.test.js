import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

test('LINE OA confirmation uses GunGong logo instead of a question icon', () => {
  const source = readFileSync(new URL('../src/shared/layout/TopBanner.jsx', import.meta.url), 'utf8');
  assert.match(source, /imageUrl: '\/img\/logo.png'/u);
  assert.match(source, /imageAlt: 'GunGong'/u);
  assert.doesNotMatch(source, /icon: 'question'/u);
  assert.match(source, /preConfirm: \(\) => \{ window.open\(LINE_OA_URL, '_blank', 'noopener,noreferrer'\)/u);
  assert.match(source, /showCancelButton: true/u);
});

test('LINE OA popup enlarges the logo and matches Report text and Scanner button colors', () => {
  const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
  const source = read('../src/shared/layout/TopBanner.jsx');
  const css = read('../src/shared/styles/main.css');
  const report = read('../src/features/report/report.css');
  const scanner = read('../src/features/scanner/scanner.css');
  assert.match(source, /imageWidth: 120/u);
  assert.match(source, /imageHeight: 120/u);
  assert.match(source, /popup: 'line-oa-popup'/u);
  const textColor = report.match(/\.report-form legend \{ color: ([^;]+);/u)[1];
  const buttonColor = scanner.match(/\.form-submit-btn \{[^}]*background: ([^;]+);/u)[1];
  assert.equal(css.match(/\.line-oa-popup \.swal2-html-container \{\s*color: ([^ ]+) !important;/u)[1], textColor);
  assert.match(css, /\.line-oa-popup \.swal2-title,\s*\.line-oa-popup \.swal2-html-container/u);
  assert.ok(source.includes(`confirmButtonColor: '${buttonColor}'`));
  assert.match(source, /cancelButtonColor: '#e5e7eb'/u);
  assert.match(css, /\.line-oa-popup \.swal2-cancel \{ color: #6d6d6d !important;/u);
});
