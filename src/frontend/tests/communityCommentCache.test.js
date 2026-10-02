import assert from 'node:assert/strict';
import test from 'node:test';
import { communityCommentCache, readCommunityComments, mergeCommunityComments } from '../src/features/community/utils/communityCommentCache.js';

const id = 'a'.repeat(64);
test('opening the same post shares one comments request and caches successful results', async () => {
    const original = globalThis.fetch; let count = 0;
    globalThis.window = { location: { origin: 'https://app.test', hostname: 'app.test' } };
    globalThis.fetch = async () => { count++; return new Response(JSON.stringify({ comments: [{ id: 'one' }], next_cursor: 'more' })); };
    communityCommentCache.invalidate();
    try {
        await Promise.all([readCommunityComments(id), readCommunityComments(id)]);
        await readCommunityComments(id);
        assert.equal(count, 1);
        assert.equal(communityCommentCache.peek('b'.repeat(64)), undefined);
        mergeCommunityComments(id, [{ id: 'one' }, { id: 'two' }], null);
        mergeCommunityComments(id, [{ id: 'new' }]);
        assert.deepEqual((await readCommunityComments(id)).comments.map(comment => comment.id), ['one', 'two', 'new']);
        assert.equal(count, 1);
        assert.equal(communityCommentCache.peek(id).next_cursor, null);
    } finally { communityCommentCache.invalidate(); globalThis.fetch = original; delete globalThis.window; }
});

test('expired comments stay visible while refreshing; not-found and malformed results are not cached', async () => {
    const original = globalThis.fetch;
    globalThis.window = { location: { origin: 'https://app.test', hostname: 'app.test' } };
    communityCommentCache.write(id, { comments: [{ id: 'old' }], next_cursor: null });
    communityCommentCache.expire(id);
    let finish;
    globalThis.fetch = () => new Promise(resolve => { finish = resolve; });
    try {
        const pending = readCommunityComments(id); await Promise.resolve();
        assert.equal(communityCommentCache.peek(id).comments[0].id, 'old');
        finish(new Response(JSON.stringify({ comments: [{ id: 'fresh' }], next_cursor: null })));
        await pending; assert.equal(communityCommentCache.peek(id).comments[0].id, 'fresh');
        communityCommentCache.expire(id);
        globalThis.fetch = async () => new Response('{}', { status: 404 });
        await assert.rejects(readCommunityComments(id), /POST_NOT_FOUND/u);
        assert.equal(communityCommentCache.peek(id), undefined);
        globalThis.fetch = async () => new Response('{}');
        await assert.rejects(readCommunityComments(id), /COMMUNITY_UNAVAILABLE/u);
        assert.equal(communityCommentCache.peek(id), undefined);
    } finally { communityCommentCache.invalidate(); globalThis.fetch = original; delete globalThis.window; }
});

test('a comment saved during refresh cannot be replaced by its older response', async () => {
    const original = globalThis.fetch;
    globalThis.window = { location: { origin: 'https://app.test', hostname: 'app.test' } };
    let finish;
    globalThis.fetch = () => new Promise(resolve => { finish = resolve; });
    try {
        const pending = readCommunityComments(id); await Promise.resolve();
        mergeCommunityComments(id, [{ id: 'saved' }]);
        finish(new Response(JSON.stringify({ comments: [], next_cursor: null })));
        await assert.rejects(pending, /CACHE_INVALIDATED/u);
        assert.equal(communityCommentCache.peek(id).comments[0].id, 'saved');
    } finally { communityCommentCache.invalidate(); globalThis.fetch = original; delete globalThis.window; }
});
