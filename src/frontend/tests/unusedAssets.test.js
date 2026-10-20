import assert from 'node:assert/strict';
import test from 'node:test';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
function files(folder) {
  return readdirSync(folder, { withFileTypes: true }).flatMap(entry => {
    const target = path.join(folder, entry.name);
    return entry.isDirectory() ? files(target) : [target];
  });
}
const activeCode = files(path.join(root, 'src')).filter(file => /\.(js|jsx|css)$/u.test(file))
  .map(file => readFileSync(file, 'utf8')).join('\n') + readFileSync(path.join(root, 'index.html'), 'utf8');

test('each shipped image is referenced and all literal local image paths resolve', () => {
  const imageRoot = path.join(root, 'public/img');
  const shipped = files(imageRoot);
  assert.ok(shipped.length > 0);
  for (const file of shipped) {
    const asset = 'img/' + path.relative(imageRoot, file).split(path.sep).join('/');
    assert.ok(activeCode.includes(asset), `Unreferenced public asset: ${asset}`);
  }
  for (const [, asset] of activeCode.matchAll(/['"`]\/?(img\/[^'"`\n]+?\.(?:png|jpe?g|webp|svg))['"`]/gu)) {
    assert.ok(existsSync(path.join(root, 'public', asset)), `Missing public asset: ${asset}`);
  }
});

test('scanner and helpers contain no retired personal checks or identity cards', () => {
  for (const file of ['src/features/scanner/scanner.jsx', 'src/features/scanner/ScanImage.jsx',
    'src/features/auth/liff.js', 'src/shared/api/script.js']) {
    assert.doesNotMatch(readFileSync(path.join(root, file), 'utf8'),
      /checkPhone|checkBank|check-personal|verify-id-card|id-card-scanner|shareVerificationCard|บัตรประชาชน/u);
  }
});
