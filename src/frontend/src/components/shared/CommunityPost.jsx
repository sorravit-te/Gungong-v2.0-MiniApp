import { useEffect, useRef, useState } from 'react';
import { commentCommunityPost, communityError, getCommunityImageUrl, getCommunityPost,
    loadPostComments, postExcerpt, reportCommunityPost } from '../../utils/community';
import { communityCommentCache, mergeCommunityComments, readCommunityComments } from '../../utils/communityCommentCache';
import { communityAvatarUrl, communityTimestamp } from '../../utils/communityPresentation';

function CommunityAvatar({ url, name }) {
    const [failed, setFailed] = useState(null);
    const src = communityAvatarUrl(url);
    return <span className="community-avatar">
        {src && failed !== src ? <img src={src} alt={`รูปโปรไฟล์ของ ${name}`} loading="lazy" referrerPolicy="no-referrer"
            onError={() => setFailed(src)} /> : <svg viewBox="0 0 24 24" role="img" aria-label={`รูปโปรไฟล์สำรองของ ${name}`}>
            <circle cx="12" cy="8" r="4" fill="currentColor" />
            <path d="M4 22v-3a8 8 0 0 1 16 0v3Z" fill="currentColor" />
        </svg>}
    </span>;
}

function Heart({ filled }) {
    return <svg viewBox="0 0 24 24" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />
    </svg>;
}

export function CommunityPostCard({ post, viewer = {}, full = false, liking, onLike, onOpen, onImage, onEdit, onDelete, onReport }) {
    const excerpt = postExcerpt(post.content);
    const image = getCommunityImageUrl(post);
    const openCard = event => {
        if (full || event.target.closest('button, details, a, input, textarea, select')) return;
        onOpen(post);
    };
    const closeOtherMenus = event => {
        if (!event.target.closest('summary')) return;
        const current = event.currentTarget;
        document.querySelectorAll('.community-post-menu[open]').forEach(menu => {
            if (menu !== current) menu.open = false;
        });
    };
    return <article className={`social-card${full ? '' : ' community-clickable-post'}`}
        tabIndex={full ? undefined : 0} aria-label={full ? undefined : `ดูโพสต์ของ ${post.author}`}
        onClick={openCard} onKeyDown={event => {
            if (!full && event.target === event.currentTarget && ['Enter', ' '].includes(event.key)) {
                event.preventDefault(); onOpen(post);
            }
        }}>
        <div className="s-card-content">
            <div className="s-card-top"><div className="author-info">
                <CommunityAvatar url={post.author_picture_url} name={post.author} />
                <div className="author-details">
                <span className="author-name">{post.author}</span>
                <span className="post-time">{communityTimestamp(post.created_at)}
                    {post.updated_at && ' · แก้ไขแล้ว'}</span>
            </div></div><details className="community-post-menu" name="community-post-menu" onClick={closeOtherMenus}>
                <summary aria-label="ตัวเลือกโพสต์">···</summary>
                <div>
                    {viewer.can_edit && <><button type="button" onClick={() => onEdit(post)}>แก้ไขโพสต์</button>
                        <button type="button" onClick={() => onDelete(post)}>ลบโพสต์</button></>}
                    <button type="button" onClick={() => onReport(post)}>รายงานโพสต์</button>
                </div>
            </details></div>
            {post.content && <div className="community-post-copy">
                <p className="post-text">{full ? post.content : excerpt.text}{!full && excerpt.truncated && '…'}</p>
                {!full && excerpt.truncated && <button className="community-more-text" type="button" onClick={() => onOpen(post)}>ดูเพิ่มเติม</button>}
            </div>}
            {image && <button type="button" className="community-image-button" aria-label="ดูรูปเต็ม" onClick={() => onImage(image)}>
                <img className="post-image" loading="lazy" src={image} alt="ภาพแนบในโพสต์" />
            </button>}
            <div className="community-post-actions">
                <button type="button" className={`community-heart ${viewer.liked ? 'liked' : ''}`}
                    aria-label={viewer.liked ? 'เลิกถูกใจ' : 'ถูกใจ'} aria-pressed={!!viewer.liked} disabled={liking}
                    onClick={() => onLike(post)}><Heart filled={viewer.liked} /><span>{post.like_count || 0}</span></button>
                <button type="button" onClick={() => onOpen(post)} aria-label="ดูความคิดเห็น">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                        <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2V11.5a9.5 9.5 0 1 1 19 0Z" />
                    </svg><span>{post.comment_count || 0}</span>
                </button>
            </div>
        </div>
    </article>;
}

export function CommunityPostDetail({ post, onBack, onUpdate, ...actions }) {
    const cached = communityCommentCache.peek(post.id);
    const [comments, setComments] = useState(cached?.comments || []);
    const [cursor, setCursor] = useState(cached?.next_cursor || null);
    const [loading, setLoading] = useState(!cached);
    const [sending, setSending] = useState(false);
    const [content, setContent] = useState('');
    const [error, setError] = useState('');
    const pending = useRef(null);
    const alive = useRef(false);
    useEffect(() => {
        alive.current = true;
        let stopped = false;
        let postMissing = false;
        // Comments need not wait for the separate post refresh to finish.
        getCommunityPost(post.id).then(fresh => { if (!stopped) onUpdate(fresh); })
            .catch(failure => {
                if (stopped) return;
                if (failure.message === 'POST_NOT_FOUND') {
                    postMissing = true; communityCommentCache.invalidate(post.id);
                    setComments([]); setCursor(null);
                }
                setError(communityError(failure));
            });
        readCommunityComments(post.id).then(result => {
            if (stopped || postMissing) return;
            setComments(result.comments); setCursor(result.next_cursor);
        }).catch(failure => {
            if (stopped) return;
            if (failure.message === 'CACHE_INVALIDATED') {
                const latest = communityCommentCache.peek(post.id);
                if (latest) { setComments(latest.comments); setCursor(latest.next_cursor); }
                return;
            }
            if (failure.message === 'POST_NOT_FOUND') { setComments([]); setCursor(null); }
            setError(communityError(failure));
        })
            .finally(() => { if (!stopped) setLoading(false); });
        return () => { stopped = true; alive.current = false; };
    }, [post.id, onUpdate]);

    const submit = async event => {
        event.preventDefault();
        if (sending || !content.trim()) return;
        setSending(true); setError('');
        pending.current ??= { content: content.trim(), id: crypto.randomUUID() };
        try {
            const result = await commentCommunityPost(post.id, pending.current.content, pending.current.id);
            const merged = mergeCommunityComments(post.id, [result.comment]);
            onUpdate({ id: post.id, comment_count: result.comment_count });
            if (!alive.current) return;
            setComments(merged.comments); setCursor(merged.next_cursor);
            setContent(''); pending.current = null;
        } catch (failure) { if (alive.current) setError(communityError(failure)); }
        finally { if (alive.current) setSending(false); }
    };
    const more = async () => {
        if (loading || !cursor) return;
        setLoading(true);
        try {
            const result = await loadPostComments(post.id, cursor);
            const merged = mergeCommunityComments(post.id, result.comments, result.next_cursor);
            if (!alive.current) return;
            setComments(merged.comments); setCursor(merged.next_cursor); setError('');
        } catch (failure) { if (alive.current) setError(communityError(failure)); }
        finally { if (alive.current) setLoading(false); }
    };
    return <div className="community-post-detail">
        <button className="community-back" type="button" onClick={onBack}>← กลับ Community</button>
        <div className="community-detail-layout">
        <div className="community-detail-post">
            <CommunityPostCard post={post} {...actions} full onOpen={() => document.getElementById('community-comment-input')?.focus()} />
        </div>
        <section className="community-comments" aria-label="ความคิดเห็น">
            <h3>ความคิดเห็น</h3>
            {comments.map(comment => <div className="community-comment" key={comment.id}>
                <div className="community-comment-author">
                    <CommunityAvatar url={comment.author_picture_url} name={comment.author} />
                    <div className="community-comment-meta"><strong>{comment.author}</strong>
                        {communityTimestamp(comment.created_at) && <time className="post-time" dateTime={comment.created_at}>
                            {communityTimestamp(comment.created_at)}
                        </time>}
                    </div>
                </div>
                <p>{comment.content}</p>
            </div>)}
            {loading && <p className="page-loading" role="status">กำลังโหลดความคิดเห็น...</p>}
            {!loading && !error && comments.length === 0 && <p className="page-loading">ยังไม่มีคอมเมนต์</p>}
            {cursor && <button type="button" disabled={loading} onClick={more}>ดูความคิดเห็นเพิ่มเติม</button>}
            <form onSubmit={submit} className="community-comment-form">
                <textarea id="community-comment-input" aria-label="ความคิดเห็น" placeholder="เพิ่มความคิดเห็น..." maxLength={1000}
                    value={content} disabled={sending} onChange={event => { setContent(event.target.value); pending.current = null; }} />
                <button type="submit" disabled={sending || !content.trim()}>{sending ? 'กำลังส่ง...' : 'ส่ง'}</button>
            </form>
            {error && <p role="alert">{error}</p>}
        </section>
        </div>
    </div>;
}

function useModal(ref) {
    useEffect(() => {
        const element = ref.current;
        const previous = document.body.style.overflow;
        element.showModal(); document.body.style.overflow = 'hidden';
        return () => { element.close(); document.body.style.overflow = previous; };
    }, [ref]);
}

export function CommunityImageViewer({ src, onClose }) {
    const dialog = useRef(null); useModal(dialog);
    return <dialog ref={dialog} className="community-full-image" aria-label="ภาพเต็ม" onCancel={onClose}>
        <button type="button" className="community-close" aria-label="ปิดภาพ" onClick={onClose}>×</button>
        <img src={src} alt="ภาพเต็มจากโพสต์" />
    </dialog>;
}

export function CommunityReportDialog({ post, onClose, onSaved }) {
    const dialog = useRef(null); useModal(dialog);
    const [reason, setReason] = useState('scam');
    const [details, setDetails] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const alive = useRef(true);
    useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
    const submit = async event => {
        event.preventDefault(); if (saving) return;
        setSaving(true); setError('');
        try {
            await reportCommunityPost(post.id, reason, details);
            if (alive.current) onSaved();
        } catch (failure) { if (alive.current) setError(communityError(failure)); }
        finally { if (alive.current) setSaving(false); }
    };
    return <dialog ref={dialog} className="community-report-dialog" aria-labelledby="community-report-title"
        onCancel={event => { if (saving) event.preventDefault(); else onClose(); }}>
        <form onSubmit={submit}>
            <div className="community-composer-header"><h3 id="community-report-title">รายงานโพสต์</h3>
                <button type="button" className="community-close" disabled={saving} onClick={onClose} aria-label="ปิดรายงาน">×</button></div>
            <label>เหตุผล<select value={reason} disabled={saving} onChange={event => setReason(event.target.value)}>
                <option value="scam">สงสัยหลอกลวง</option><option value="phishing">ฟิชชิ่ง / ขโมยข้อมูล</option>
                <option value="risky">เนื้อหามีความเสี่ยง</option><option value="other">อื่น ๆ</option>
            </select></label>
            <textarea aria-label="รายละเอียดรายงาน" maxLength={500} placeholder="รายละเอียดเพิ่มเติม (ไม่บังคับ)"
                value={details} disabled={saving} onChange={event => setDetails(event.target.value)} />
            <p>รายงานจะถูกบันทึกเพื่อรอตรวจสอบ ไม่ใช่การยืนยันว่าโพสต์นี้หลอกลวง</p>
            {error && <p role="alert">{error}</p>}
            <button type="submit" className="community-submit" disabled={saving}>{saving ? 'กำลังส่ง...' : 'ส่งรายงาน'}</button>
        </form>
    </dialog>;
}
