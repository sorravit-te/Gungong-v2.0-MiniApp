import { createPageCache } from './pageCache.js';
import { loadPostComments } from './community.js';

// Public comments only, keyed by post. Revalidate after the shared 30-second TTL.
export const communityCommentCache = createPageCache();

export function readCommunityComments(id) {
    return communityCommentCache.read(id, async () => {
        const result = await loadPostComments(id);
        if (!Array.isArray(result.comments)) throw new Error('COMMUNITY_UNAVAILABLE');
        return result;
    }).catch(error => {
        if (error.message === 'POST_NOT_FOUND') communityCommentCache.invalidate(id);
        throw error;
    });
}

export function mergeCommunityComments(id, comments, nextCursor) {
    const previous = communityCommentCache.peek(id);
    const result = {
        comments: [...(previous?.comments || []), ...comments.filter(comment =>
            !previous?.comments.some(old => old.id === comment.id))],
        next_cursor: nextCursor === undefined ? previous?.next_cursor || null : nextCursor,
    };
    communityCommentCache.write(id, result);
    return result;
}
