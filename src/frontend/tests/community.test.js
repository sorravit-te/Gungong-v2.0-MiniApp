import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { getSessionHeaders } from '../src/utils/session.js';
import { getCommunityImageUrl, loadCommunity, postCommunity, postExcerpt, likeCommunityPost,
  commentCommunityPost, editCommunityPost, deleteCommunityPost, reportCommunityPost } from '../src/utils/community.js';
import { validateImageFile } from '../src/utils/communityImage.js';

test('public feed is real bounded API data, with encoded cursor and no author identity', async () => {
  globalThis.window = { location: { origin: 'https://app.test', hostname: 'app.test' } };
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ posts: [{ id: 'one', content: '<script>literal</script>' }], next_cursor: null }));
  };
  try {
    const feed = await loadCommunity('cursor/value');
    assert.equal(feed.posts[0].content, '<script>literal</script>');
    assert.equal(calls[0].url, 'https://app.test/community/posts?after=cursor%2Fvalue');
    assert.equal(calls[0].options.cache, 'no-store');
    assert.ok(calls[0].options.signal instanceof AbortSignal);
    assert.equal(calls[0].options.headers, undefined);
  } finally { globalThis.fetch = original; }
});

test('posting sends verified session token, same retry ID, and no forged author/user ID', async () => {
  globalThis.window.liff = { isLoggedIn: () => true, getAccessToken: () => 'test-only-token' };
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push(options); return new Response(JSON.stringify({ id: 'saved', content: 'Post' }));
  };
  try {
    await postCommunity('Post', 'stable-id'); await postCommunity('Post', 'stable-id');
    assert.deepEqual(JSON.parse(calls[0].body), { content: 'Post', request_id: 'stable-id' });
    assert.equal(calls[0].body, calls[1].body);
    assert.equal(calls[0].headers.Authorization, 'Bearer test-only-token');
    assert.equal(calls[0].headers['X-Auth-Provider'], 'line');
  } finally { globalThis.fetch = original; delete globalThis.window.liff; }
});

test('anonymous session cannot post and failed reads do not become mock success', async () => {
  await assert.rejects(getSessionHeaders(), /LOGIN_REQUIRED/u);
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response('{}', { status: 503 });
  try { await assert.rejects(loadCommunity(), /COMMUNITY_UNAVAILABLE/u); }
  finally { globalThis.fetch = original; }
});

test('community/history refresh on return and only render user text, no mock interactions', () => {
  const social = readFileSync(new URL('../src/components/social.jsx', import.meta.url), 'utf8');
  const history = readFileSync(new URL('../src/components/history.jsx', import.meta.url), 'utf8');
  const historyLoader = readFileSync(new URL('../src/hooks/useHistoryEntries.js', import.meta.url), 'utf8');
  assert.match(history, /useHistoryEntries\(\)/u);
  for (const source of [social, historyLoader]) {
    assert.match(source, /visibilitychange/u);
    assert.match(source, /addEventListener\('focus'/u);
    assert.match(source, /removeEventListener\('focus'/u);
    assert.match(source, /30000/u);
  }
  assert.doesNotMatch(social, /dangerouslySetInnerHTML|Somsak|post\.likes|post\.comments/u);
  const cards = readFileSync(new URL('../src/components/shared/CommunityPost.jsx', import.meta.url), 'utf8');
  assert.doesNotMatch(cards, /dangerouslySetInnerHTML/u);
  assert.match(cards, /full \? post\.content : excerpt\.text/u);
});

test('composer is a dialog with attachment preview; old inline submit and copy are gone', () => {
  const social = readFileSync(new URL('../src/components/social.jsx', import.meta.url), 'utf8');
  const css = readFileSync(new URL('../src/styles/social.css', import.meta.url), 'utf8');
  assert.match(social, /aria-haspopup="dialog"/u);
  assert.match(social, /element\.showModal\(\)/u);
  assert.match(social, /aria-labelledby="community-composer-title"/u);
  assert.match(social, /type="file" accept="image\/jpeg,image\/png,image\/webp"/u);
  assert.match(social, /ตัวอย่างภาพก่อนโพสต์/u);
  assert.match(social, /เอาภาพออก/u);
  assert.doesNotMatch(social, /โพสต์ในหน้านี้แสดงให้ผู้ใช้อื่นเห็น|ยังไม่มีโพสต์ เป็นคนแรก|add-post-btn/u);
  assert.match(css, /#social-page \.scanner-header h2 \{ margin-left: 0;/u);
});

test('post image URLs are same-origin, ID-bound and never user-controlled external URLs', () => {
  assert.equal(getCommunityImageUrl({ id: 'a'.repeat(64), has_image: true }),
    'https://app.test/community/posts/' + 'a'.repeat(64) + '/image');
  for (const id of ['https://evil.test/', '../escape', 'javascript:alert(1)']) {
    assert.equal(getCommunityImageUrl({ id, has_image: true }), null);
  }
  assert.equal(getCommunityImageUrl({ id: 'a'.repeat(64), has_image: false }), null);
});

test('community feed spans the main content area while the composer stays centered and narrow', () => {
  const css = readFileSync(new URL('../src/styles/social.css', import.meta.url), 'utf8');
  assert.match(css, /#social-page \.section-content\s*\{\s*max-width: none;/u);
  assert.match(css, /#social-page \.scanner-header,\s*#social-page \.community-compose-trigger\s*\{\s*max-width: 480px;\s*margin-inline: auto;/u);
  assert.match(css, /grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/u);
  assert.match(css, /@media \(max-width: 1100px\).*repeat\(2, minmax\(0, 1fr\)\)/u);
  assert.match(css, /@media \(max-width: 700px\)\s*\{\s*\.social-feed \{ grid-template-columns: minmax\(0, 1fr\); padding-inline: 0; max-width: 480px; margin-inline: auto; \}\s*\.community-feed-item \{ width: 100%; \}/u);
});

test('attachments reject unsupported files and oversized originals before decoding', () => {
  assert.doesNotThrow(() => validateImageFile({ type: 'image/jpeg', size: 100 }));
  for (const file of [{ type: 'image/svg+xml', size: 100 }, { type: 'image/png', size: 11 * 1024 * 1024 },
                      { type: 'image/jpeg', size: 0 }]) assert.throws(() => validateImageFile(file));
});

test('image is carried in the same authenticated idempotent post, not a separate orphan upload', async () => {
  globalThis.window.liff = { isLoggedIn: () => true, getAccessToken: () => 'test-only-token' };
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push(options); return new Response(JSON.stringify({ id: 'saved', has_image: true }));
  };
  try {
    await postCommunity('', 'stable-id', 'base64-fixture');
    assert.deepEqual(JSON.parse(calls[0].body), { content: '', request_id: 'stable-id', image: 'base64-fixture' });
    assert.equal(calls[0].headers['X-Auth-Provider'], 'line');
  } finally { globalThis.fetch = original; delete globalThis.window.liff; }
});

test('excerpt keeps full content available and truncates unicode or many lines', () => {
  assert.deepEqual(postExcerpt('Short'), { text: 'Short', truncated: false });
  assert.equal(Array.from(postExcerpt('😀'.repeat(200)).text).length, 180);
  assert.equal(postExcerpt('😀'.repeat(200)).truncated, true);
  assert.equal(postExcerpt('a\nb\nc\nd\ne').text, 'a\nb\nc\nd');
});

test('real social mutations carry verified identity, bounded IDs and expected revision', async () => {
  globalThis.window.liff = { isLoggedIn: () => true, getAccessToken: () => 'test-only-token' };
  const original = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return new Response('{}'); };
  const id = 'a'.repeat(64);
  try {
    await likeCommunityPost(id, true);
    await commentCommunityPost(id, 'Comment', 'stable-id');
    await editCommunityPost(id, { content: 'Edit', expected_revision: 2 });
    await deleteCommunityPost(id);
    await reportCommunityPost(id, 'scam');
    assert.deepEqual(calls.map(item => item.options.method), ['PUT', 'POST', 'PATCH', 'DELETE', 'PUT']);
    for (const item of calls) {
      assert.equal(item.options.headers.Authorization, 'Bearer test-only-token');
      assert.ok(item.options.signal instanceof AbortSignal);
      assert.doesNotMatch(item.options.body || '', /author_id|user_id/u);
    }
    assert.equal(JSON.parse(calls[2].options.body).expected_revision, 2);
    assert.throws(() => deleteCommunityPost('../escape'), /POST_NOT_FOUND/u);
    assert.equal(getCommunityImageUrl({ id, has_image: true, image_version: 'b'.repeat(64) }),
      `https://app.test/community/posts/${id}/image?v=${'b'.repeat(64)}`);
  } finally { globalThis.fetch = original; delete globalThis.window.liff; }
});

test('post detail keeps post left and comments right on desktop and stacks on mobile', () => {
  const cards = readFileSync(new URL('../src/components/shared/CommunityPost.jsx', import.meta.url), 'utf8');
  const css = readFileSync(new URL('../src/styles/social.css', import.meta.url), 'utf8');
  assert.match(cards, /className="community-detail-layout"/u);
  assert.match(cards, /className="community-detail-post"/u);
  assert.ok(cards.indexOf('className="community-detail-post"') < cards.indexOf('className="community-comments"'));
  assert.match(css, /\.community-detail-layout \{ display: grid; grid-template-columns: minmax\(0, \.9fr\) minmax\(0, 1\.1fr\)/u);
  assert.match(css, /@media \(max-width: 900px\).*\.community-detail-layout \{ grid-template-columns: minmax\(0, 1fr\)/u);
});

test('cards open separately from image/actions and menus are exclusive and dismissible', () => {
  const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
  const cards = read('../src/components/shared/CommunityPost.jsx');
  const social = read('../src/components/social.jsx');
  assert.match(social, /<h2>Community<\/h2>/u);
  assert.match(cards, /event\.target\.closest\('button, details, a, input, textarea, select'\)/u);
  assert.match(cards, /event\.target === event\.currentTarget/u);
  assert.match(cards, /if \(menu !== current\) menu\.open = false/u);
  assert.match(social, /!menu\.contains\(event\.target\)/u);
  assert.match(social, /removeEventListener\('pointerdown', closeMenus\)/u);
  assert.doesNotMatch(cards, /Promise\.all\(\[getCommunityPost/u);
});

test('post cards stay stationary and full images have rounded corners without a dark frame', () => {
  const css = readFileSync(new URL('../src/styles/social.css', import.meta.url), 'utf8');
  assert.doesNotMatch(css, /translateY|scale\(0\.98\)/u);
  assert.match(css, /\.community-full-image \{[^}]*padding: 0;[^}]*background: transparent/u);
  assert.match(css, /\.community-full-image > img \{[^}]*border-radius: 16px/u);
});

test('whole feed cards are inset and the sidebar starts collapsed until toggled', () => {
  const css = readFileSync(new URL('../src/styles/social.css', import.meta.url), 'utf8');
  const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');
  assert.match(css, /\.community-feed-item \{ width: 94%; min-width: 0; justify-self: center;/u);
  assert.match(css, /\.social-feed \.social-card \{ width: 100%;/u);
  assert.match(css, /padding-inline: clamp\(8px, 1\.5vw, 24px\)/u);
  assert.doesNotMatch(css, /\.social-feed \.post-image/u);
  assert.match(app, /\[isSidebarCollapsed, setIsSidebarCollapsed\] = useState\(true\)/u);
  assert.match(app, /setIsSidebarCollapsed\(prev => !prev\)/u);
});

test('LINE login keeps the original width with a reduced height and card hover changes only the faint border', () => {
  const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
  assert.match(read('../src/styles/auth.css'), /\.sidebar-login-btn\.line-login-btn \{ width: 100%; height: 44px;/u);
  assert.match(read('../src/styles/social.css'), /\.social-feed \.social-card:hover \{ border-color: #d1d5db; \}/u);
  assert.match(read('../src/components/shared/CommunityPost.jsx'), /readCommunityComments\(post\.id\)/u);
  assert.match(read('../src/components/social.jsx'), /communityCommentCache\.invalidate\(post\.id\)/u);
});

test('post details hide the feed heading and show avatars alongside unchanged names and comment timestamps', () => {
  const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
  const cards = read('../src/components/shared/CommunityPost.jsx');
  const social = read('../src/components/social.jsx');
  assert.match(social, /!selected && <div className="scanner-header"/u);
  assert.match(social, /if \(selectedId\) window\.scrollTo\(0, 0\)/u);
  assert.match(cards, /url=\{post\.author_picture_url\}/u);
  assert.match(cards, /url=\{comment\.author_picture_url\}/u);
  assert.match(cards, /<strong>\{comment\.author\}<\/strong>/u);
  assert.match(cards, /dateTime=\{comment\.created_at\}/u);
  assert.match(cards, /onError=\{\(\) => setFailed\(src\)\}/u);
});

test('back to Community uses the same green heading size in light and dark mode', () => {
  const css = readFileSync(new URL('../src/styles/social.css', import.meta.url), 'utf8');
  const scanner = readFileSync(new URL('../src/styles/scanner.css', import.meta.url), 'utf8');
  assert.match(scanner, /\.scanner-header h2 \{\s*font-size: 20px;\s*color: #3ACE00;/u);
  assert.match(css, /\.community-back \{ margin-bottom: 12px; color: #3ACE00; font-size: 20px; font-weight: 700;/u);
  assert.doesNotMatch(css, /html\.dark-mode \.community-back/u);
});

test('empty comments are shown only after a successful load, not during loading or errors', () => {
  const cards = readFileSync(new URL('../src/components/shared/CommunityPost.jsx', import.meta.url), 'utf8');
  assert.match(cards, /!loading && !error && comments\.length === 0 && <p className="page-loading">ยังไม่มีคอมเมนต์<\/p>/u);
});

test('empty public feed has a message only after a successful empty load', () => {
  const social = readFileSync(new URL('../src/components/social.jsx', import.meta.url), 'utf8');
  assert.match(social, /!loading && !error && posts\.length === 0 && !cursor && <p className="page-loading">ยังไม่มีโพสต์<\/p>/u);
});
