import assert from 'node:assert/strict';
import test from 'node:test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../src/', import.meta.url));
function sources(folder) {
  return readdirSync(folder, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(folder, entry.name);
    return entry.isDirectory() ? sources(file) : /\.(js|jsx)$/u.test(file) ? [file] : [];
  });
}

test('all active relative imports and the QR worker resolve', () => {
  let checked = 0;
  for (const file of sources(root)) {
    const source = readFileSync(file, 'utf8');
    const imports = /(?:\bfrom\s*|\bimport\s*\(?\s*|new URL\(\s*)['"](\.[^'"]+)['"]/gu;
    for (const [, specifier] of source.matchAll(imports)) {
      const target = path.resolve(path.dirname(file), specifier);
      assert.ok(['', '.js', '.jsx', '.css'].some(extension => existsSync(target + extension)),
        `${path.relative(root, file)}: missing ${specifier}`);
      checked++;
    }
  }
  assert.ok(checked > 80);
});

test('feature boundaries and stable entrypoints are explicit without old catch-all folders', () => {
  for (const feature of ['home', 'community', 'scanner', 'history', 'report', 'auth', 'privacy']) {
    assert.ok(existsSync(path.join(root, 'features', feature)));
  }
  for (const shared of ['layout', 'navigation', 'api', 'cache', 'results', 'qr', 'styles']) {
    assert.ok(existsSync(path.join(root, 'shared', shared)));
  }
  assert.ok(existsSync(path.join(root, 'App.jsx')));
  assert.ok(existsSync(path.join(root, 'main.jsx')));
  const app = readFileSync(path.join(root, 'App.jsx'), 'utf8');
  assert.match(app, /features\/report\/report/u);
  assert.doesNotMatch(app, /case 'verify'|import Verify|import IDCardScanner/u);
  assert.equal(existsSync(path.join(root, 'legacy/verify/verify.jsx')), false);
});
