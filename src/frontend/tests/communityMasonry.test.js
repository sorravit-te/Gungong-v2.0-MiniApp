import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { communityMasonryLayout } from '../src/utils/communityMasonry.js';

test('short text-only posts leave room for the next posts without waiting for a tall image post', () => {
    const positions = communityMasonryLayout([200, 200, 600, 400, 400], 3);
    assert.deepEqual(positions.slice(0, 3), [
        { row: 1, column: 1, span: 54 },
        { row: 1, column: 2, span: 54 },
        { row: 1, column: 3, span: 154 },
    ]);
    assert.equal(positions[3].row, 55);
    assert.equal(positions[4].row, 55);
});

test('responsive measurement clears old explicit grid positions before reading the column count', () => {
    const source = readFileSync(new URL('../src/components/shared/CommunityFeed.jsx', import.meta.url), 'utf8');
    assert.ok(source.indexOf("item.style.gridArea = ''") < source.indexOf('getComputedStyle(element)'));
    assert.match(source, /observer\.observe\(item\.firstElementChild\)/u);
    assert.match(source, /observer\.disconnect\(\); cancelAnimationFrame\(frame\)/u);
});

test('every card has a non-overlapping slot and a small consistent gap at all responsive column counts', () => {
    const heights = [180, 550, 201, 400, 130, 800];
    for (const columns of [1, 2, 3]) {
        const positions = communityMasonryLayout(heights, columns);
        const ends = Array(columns).fill(1);
        positions.forEach((position, index) => {
            assert.equal(position.row, ends[position.column - 1]);
            const gap = position.span * 4 - heights[index];
            assert.ok(gap >= 16 && gap < 20);
            ends[position.column - 1] = position.row + position.span;
        });
    }
    assert.deepEqual(communityMasonryLayout([], 3), []);
});
