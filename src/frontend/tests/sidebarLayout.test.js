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

test('profile popup escapes sidebar clipping and shares its existing animation with History', () => {
    const source = read('../src/components/shared/Sidebar.jsx');
    const css = read('../src/styles/sidebar.css');
    const historyCss = read('../src/styles/history.css');
    assert.match(source, /showUserMenu && createPortal\(/u);
    assert.match(source, /<\/div>, document\.body/u);
    assert.match(source, /!userPopupRef\.current\?\.contains\(event\.target\)/u);
    assert.match(source, /event\.key === 'Escape'/u);
    assert.match(source, /observer\.observe\(anchor\)/u);
    assert.match(source, /observer\.disconnect\(\)/u);
    assert.match(source, /window\.innerWidth - width - 8/u);
    assert.match(css, /\.user-dropdown-menu \{\s*position: fixed;/u);
    assert.doesNotMatch(css, /collapsed-position/u);
    assert.match(css, /animation: dropdownFadeIn 0\.2s ease;/u);
    assert.match(historyCss, /animation: dropdownFadeIn 0\.2s ease;/u);
    assert.match(source, /canSignOut && <button className="dropdown-item logout" onClick=\{handleLogout\}/u);
});
