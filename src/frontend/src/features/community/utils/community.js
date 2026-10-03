import { getApiBaseUrl } from '../../../shared/api/script.js';
import { getSessionHeaders } from '../../auth/session.js';
import { communityCache } from '../../../shared/cache/pageCache.js';

async function request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
        const response = await fetch(`${getApiBaseUrl()}/community/posts${path}`, {
            ...options, signal: controller.signal, cache: 'no-store',
        });
        if (!response.ok) throw new Error(({ 401: 'LOGIN_REQUIRED', 403: 'OWNER_REQUIRED',
            404: 'POST_NOT_FOUND', 409: 'POST_CHANGED' })[response.status] || 'COMMUNITY_UNAVAILABLE');
        const data = await response.json();
        if (!data || typeof data !== 'object') throw new Error('COMMUNITY_UNAVAILABLE');
        return data;
    } finally { clearTimeout(timer); }
}

export async function loadCommunity(after = null) {
    const data = await request(after ? `?after=${encodeURIComponent(after)}` : '');
    if (!Array.isArray(data.posts)) throw new Error('COMMUNITY_UNAVAILABLE');
    return data;
}

export function getCommunityImageUrl(post) {
    const version = /^[a-f0-9]{64}$/u.test(post.image_version || '') ? `?v=${post.image_version}` : '';
    return post.has_image && /^[a-f0-9]{64}$/u.test(post.id)
        ? `${getApiBaseUrl()}/community/posts/${post.id}/image${version}` : null;
}

export async function postCommunity(content, requestId, image = null) {
    return request('', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...await getSessionHeaders() },
        body: JSON.stringify({ content, request_id: requestId, ...(image ? { image } : {}) }),
    });
}

function postPath(id) {
    if (!/^[a-f0-9]{64}$/u.test(id)) throw new Error('POST_NOT_FOUND');
    return `/${id}`;
}
async function mutate(path, method, body) {
    return request(path, { method,
        headers: { 'Content-Type': 'application/json', ...await getSessionHeaders() },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
}
export async function loadCommunityViewer(postIds) {
    return (await mutate('/viewer-state', 'POST', { post_ids: postIds })).states;
}
export function getCommunityPost(id) { return request(postPath(id)); }
export function readCommunityPost(id) {
    return communityCache.read(`post:${id}`, () => getCommunityPost(id));
}
export function loadPostComments(id, after = null) {
    return request(`${postPath(id)}/comments${after ? `?after=${encodeURIComponent(after)}` : ''}`);
}
export function likeCommunityPost(id, liked) { return mutate(`${postPath(id)}/like`, 'PUT', { liked }); }
export function commentCommunityPost(id, content, requestId) {
    return mutate(`${postPath(id)}/comments`, 'POST', { content, request_id: requestId });
}
export function editCommunityPost(id, changes) { return mutate(postPath(id), 'PATCH', changes); }
export function deleteCommunityPost(id) { return mutate(postPath(id), 'DELETE'); }
export function reportCommunityPost(id, reason, details = '') {
    return mutate(`${postPath(id)}/report`, 'PUT', { reason, details });
}
export function postExcerpt(content = '') {
    const text = Array.from(content);
    const short = text.slice(0, 180).join('').split('\n').slice(0, 4).join('\n');
    return { text: short, truncated: short.length < content.length };
}
export function communityError(error) {
    return ({ LOGIN_REQUIRED: 'กรุณาเข้าสู่ระบบ LINE ก่อนใช้งาน', OWNER_REQUIRED: 'แก้ไขหรือลบได้เฉพาะโพสต์ของคุณ',
        POST_NOT_FOUND: 'โพสต์นี้ถูกลบหรือไม่พบแล้ว', POST_CHANGED: 'โพสต์มีการเปลี่ยนแปลง กรุณาเปิดใหม่ก่อนแก้ไข',
    })[error.message] || 'ยังยืนยันการบันทึกไม่ได้ กรุณาโหลดใหม่เพื่อตรวจสอบก่อนลองอีกครั้ง';
}
