import assert from 'node:assert/strict';
import test from 'node:test';
import { communityAvatarUrl, communityTimestamp } from '../src/utils/communityPresentation.js';

test('community profile images accept only HTTPS LINE CDN URLs without credentials', () => {
    assert.equal(communityAvatarUrl('https://profile.line-scdn.net/picture'), 'https://profile.line-scdn.net/picture');
    for (const value of [null, '', 'javascript:alert(1)', 'data:image/png;base64,abc', 'http://profile.line-scdn.net/a',
        'https://line-scdn.net.evil.test/a', 'https://evil.test/a', 'https://user:password@profile.line-scdn.net/a']) {
        assert.equal(communityAvatarUrl(value), null);
    }
});

test('comment timestamps use Thai date and Bangkok time; missing/invalid dates are omitted', () => {
    const result = communityTimestamp('2026-10-02T09:12:34Z');
    assert.match(result, /2\/10\/2569/u);
    assert.match(result, /16:12$/u);
    assert.doesNotMatch(result, /16:12:34/u);
    for (const value of [null, '', 'bad date', undefined]) assert.equal(communityTimestamp(value), '');
});
