import { getApiBaseUrl } from './script.js';
import { getSessionHeaders } from './session.js';

async function request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
        const response = await fetch(`${getApiBaseUrl()}/community/posts${path}`, {
            ...options, signal: controller.signal, cache: 'no-store',
        });
        if (!response.ok) throw new Error(response.status === 401 ? 'LOGIN_REQUIRED' : 'COMMUNITY_UNAVAILABLE');
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
    return post.has_image && /^[a-f0-9]{64}$/u.test(post.id)
        ? `${getApiBaseUrl()}/community/posts/${post.id}/image` : null;
}

export async function postCommunity(content, requestId, image = null) {
    return request('', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...await getSessionHeaders() },
        body: JSON.stringify({ content, request_id: requestId, ...(image ? { image } : {}) }),
    });
}
