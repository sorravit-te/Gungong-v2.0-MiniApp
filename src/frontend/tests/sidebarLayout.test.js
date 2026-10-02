import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');

test('sidebar toggling hides text without replacing labels or recentering the icons', () => {
    const source = read('../src/components/shared/Sidebar.jsx');
    const css = read('../src/styles/sidebar.css');
    assert.match(source, /className="item-label" aria-hidden=\{isCollapsed\}/u);
    assert.doesNotMatch(source, /!isCollapsed && <span className="item-label"/u);
    assert.match(source, /aria-label=\{item.label\}/u);
    assert.doesNotMatch(source, /isCollapsed && groupIndex/u);
    assert.doesNotMatch(css, /\.sidebar\.collapsed \.sidebar-(?:item|brand|user) \{/u);
    assert.doesNotMatch(css, /translateX\(2px\)/u);
    assert.match(css, /\.sidebar\.collapsed \.item-label,/u);
    assert.doesNotMatch(source, /submenu-items|submenu-chevron|expandedMenus|hasSubItems/u);
    assert.match(source, /onClick=\{\(\) => onNavigate\(item\.id\)\}/u);
    assert.match(source, /item\.id === 'scanner' && SCANNER_ROUTE_IDS\.includes\(currentPage\)/u);
});

test('post details use the same page entry animation with reduced-motion support', () => {
    const css = read('../src/styles/social.css');
    assert.match(css, /\.community-post-detail \{[^}]*animation: pageSlideIn 0\.4s ease-out forwards;/u);
    assert.match(css, /prefers-reduced-motion: reduce.*\.community-post-detail \{ animation: none;/u);
});
