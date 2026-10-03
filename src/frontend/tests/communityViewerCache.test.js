import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createCommunityViewerCache } from '../src/features/community/utils/communityViewerCache.js';
import { readCommunityPost } from '../src/features/community/utils/community.js';
import { communityCache } from '../src/shared/cache/pageCache.js';

const liked = { liked: true, can_edit: false };

test('post detail reads share one request and reuse full real post on quick reopen', async () => {
    const original = globalThis.fetch; let calls = 0;
    communityCache.invalidate();
    const id = 'a'.repeat(64);
    globalThis.fetch = async () => { calls++; return new Response(JSON.stringify({ id, content: 'real API content' })); };
    try {
        const results = await Promise.all([readCommunityPost(id), readCommunityPost(id)]);
        assert.deepEqual(results[0], results[1]);
        assert.equal((await readCommunityPost(id)).content, 'real API content');
        assert.equal(calls, 1);
        communityCache.invalidate(`post:${id}`);
        await readCommunityPost(id); assert.equal(calls, 2);
    } finally { globalThis.fetch = original; communityCache.invalidate(); }
});

test('red heart is immediately retained across revisits with no second fresh read', async () => {
    const cache = createCommunityViewerCache(); let calls = 0;
    const loader = async () => { calls++; return { post: liked }; };
    await cache.read('A', ['post'], loader);
    assert.equal(cache.peek('A').post.liked, true);
    await cache.read('A', ['post'], loader);
    assert.equal(calls, 1);
    assert.deepEqual(cache.peek('B'), {});
});

test('prefetch and StrictMode consumers deduplicate the same member batch', async () => {
    const cache = createCommunityViewerCache(); let finish; let calls = 0;
    const loader = () => { calls++; return new Promise(resolve => { finish = resolve; }); };
    const first = cache.read('A', ['b', 'a', 'a'], loader);
    const second = cache.read('A', ['a', 'b'], loader);
    await Promise.resolve(); assert.equal(calls, 1);
    finish({ a: liked, b: liked });
    assert.deepEqual(await first, await second);
});

test('stale refresh keeps liked state visible; confirmed unlike wins over old response', async () => {
    let time = 0; const cache = createCommunityViewerCache({ ttl: 30, now: () => time });
    await cache.read('A', ['post'], async () => ({ post: liked }));
    time = 31; let finish;
    const work = cache.read('A', ['post'], () => new Promise(resolve => { finish = resolve; }));
    await Promise.resolve(); assert.equal(cache.peek('A').post.liked, true);
    cache.write('A', 'post', { liked: false });
    finish({ post: liked }); await work;
    assert.deepEqual(cache.peek('A').post, { liked: false, can_edit: false });
});

test('logout/account switch prevents late reads and late like confirmations restoring old data', async () => {
    const cache = createCommunityViewerCache(); let finish;
    const work = cache.read('A', ['post'], () => new Promise(resolve => { finish = resolve; }));
    await Promise.resolve(); const owner = cache.peek('A'); cache.invalidate();
    cache.write('A', 'post', liked, owner);
    finish({ post: liked }); await assert.rejects(work, /CACHE_INVALIDATED/u);
    assert.deepEqual(cache.peek('A'), {});
    await cache.read('B', ['post'], async () => ({ post: { liked: false, can_edit: true } }));
    assert.equal(cache.peek('B').post.liked, false);
});

test('401 clears member state, transient errors retain it and retry successfully', async () => {
    let time = 0; const cache = createCommunityViewerCache({ ttl: 30, now: () => time });
    await cache.read('A', ['post'], async () => ({ post: liked })); time = 31;
    await assert.rejects(cache.read('A', ['post'], async () => { throw new Error('offline'); }));
    assert.equal(cache.peek('A').post.liked, true);
    await assert.rejects(cache.read('A', ['post'], async () => { throw new Error('LOGIN_REQUIRED'); }));
    assert.deepEqual(cache.peek('A'), {});
    await cache.read('A', ['post'], async () => ({ post: liked }));
    assert.equal(cache.peek('A').post.liked, true);
});

test('missing/deleted posts remove member state and newly loaded IDs are fetched only once', async () => {
    let time = 0; const cache = createCommunityViewerCache({ ttl: 30, now: () => time });
    await cache.read('A', ['post'], async () => ({ post: liked }));
    const fetched = [];
    await cache.read('A', ['post', 'new'], async ids => { fetched.push(...ids); return { new: liked }; });
    assert.deepEqual(fetched, ['new']); time = 31;
    await cache.read('A', ['post'], async () => ({}));
    assert.equal(cache.peek('A').post, undefined);
});

test('viewer batches stay within API limit; no tokens or persistent member storage', async () => {
    const cache = createCommunityViewerCache(); const sizes = [];
    await cache.read('A', Array.from({ length: 105 }, (_, i) => String(i)), async ids => {
        sizes.push(ids.length); return Object.fromEntries(ids.map(id => [id, liked]));
    });
    assert.deepEqual(sizes, [50, 50, 5]);
    const source = readFileSync(new URL('../src/features/community/utils/communityViewerCache.js', import.meta.url), 'utf8');
    assert.doesNotMatch(source, /localStorage|sessionStorage|accessToken|Authorization/u);
});

test('navigation retains feed images and defers only heavy chart, not primary page shells', () => {
    const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
    const app = read('../src/App.jsx');
    assert.doesNotMatch(app, /กำลังโหลดหน้า|const (Home|Scanner|Social|History|Report) = lazy/u);
    assert.match(app, /<Activity key=\{user\?\.uid \|\| 'anonymous'\}/u);
    assert.match(app, /communityViewerCache\.read\(owner/u);
    assert.match(read('../src/features/community/social.jsx'), /<Activity mode=\{selected \? 'hidden' : 'visible'\}/u);
    assert.match(read('../src/features/community/components/CommunityPost.jsx'), /loading=\{full \? 'eager' : 'lazy'\}/u);
    assert.match(read('../src/features/home/components/DataVisualization.jsx'), /lazy\(\(\) => import\('\.\/SummaryResults'\)\)/u);
    assert.match(read('../src/features/history/history.jsx'), /Math\.min\(index, 3\) \* 0\.03/u);
});
