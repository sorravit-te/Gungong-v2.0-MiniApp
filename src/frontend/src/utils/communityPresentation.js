export function communityAvatarUrl(value) {
    if (typeof value !== 'string' || value.length > 2048) return null;
    try {
        const url = new URL(value);
        if (url.protocol === 'https:' && !url.username && !url.password && !url.port &&
            (url.hostname === 'line-scdn.net' || url.hostname.endsWith('.line-scdn.net'))) return url.href;
    } catch { /* Invalid and missing images use a neutral avatar. */ }
    return null;
}

export function communityTimestamp(value) {
    if (typeof value !== 'string' || !value) return '';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '';
    return date.toLocaleString('th-TH', { timeZone: 'Asia/Bangkok', year: 'numeric', month: 'numeric', day: 'numeric',
        hour: '2-digit', minute: '2-digit', hour12: false });
}
