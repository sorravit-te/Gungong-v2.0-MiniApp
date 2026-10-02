import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');

test('sidebar logo background matches the pale-green Scanner mascot background', () => {
    const sidebar = read('../src/shared/layout/sidebar.css');
    const scanner = read('../src/features/scanner/scanner.css');
    const background = source => source.match(/background:\s*([^;]+);/u)[1];
    assert.equal(background(sidebar.match(/\.brand-logo-wrapper \{([^}]+)\}/u)[1]),
        background(scanner.match(/\.scanner-feature-mascot \{([^}]+)\}/u)[1]));
});

test('Community uses the same group-of-people icon in Sidebar and BottomNav', () => {
    const icon = read('../src/shared/layout/NavigationIcon.jsx');
    assert.match(icon, /id === 'social' && <><circle cx="9" cy="7" r="4"/u);
    for (const component of ['Sidebar', 'BottomNav']) {
        assert.match(read(`../src/shared/layout/${component}.jsx`), /<NavigationIcon id=\{item.id\}/u);
    }
});

test('sidebar toggling hides text without replacing labels or recentering the icons', () => {
    const source = read('../src/shared/layout/Sidebar.jsx');
    const css = read('../src/shared/layout/sidebar.css');
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

test('post details use the same page entry animation as the other pages', () => {
    const css = read('../src/features/community/social.css');
    assert.match(css, /\.community-post-detail \{[^}]*animation: pageSlideIn 0\.4s ease-out forwards;/u);
    assert.doesNotMatch(css, /prefers-reduced-motion: reduce.*\.community-post-detail \{ animation: none;/u);
});

test('profile popup escapes sidebar clipping and shares its existing animation with History', () => {
    const source = read('../src/shared/layout/Sidebar.jsx');
    const css = read('../src/shared/layout/sidebar.css');
    const historyCss = read('../src/features/history/history.css');
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
