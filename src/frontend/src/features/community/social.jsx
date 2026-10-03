import { Activity, useCallback, useEffect, useRef, useState } from 'react';
import { communityError, deleteCommunityPost, editCommunityPost, getCommunityImageUrl, getCommunityPost,
  likeCommunityPost, loadCommunity, loadCommunityViewer, postCommunity } from './utils/community';
import { preparePostImage } from './utils/communityImage';
import { communityCache } from '../../shared/cache/pageCache';
import { communityCommentCache } from './utils/communityCommentCache';
import { communityViewerCache } from './utils/communityViewerCache';
import { useAuth } from '../auth/AuthContext';
import { CommunityPostCard, CommunityPostDetail, CommunityImageViewer, CommunityReportDialog } from './components/CommunityPost';
import CommunityFeed from './components/CommunityFeed';

const Social = () => {
  const { user } = useAuth();
  const [posts, setPosts] = useState(() => communityCache.peek('feed')?.posts || []);
  const [content, setContent] = useState('');
  const [cursor, setCursor] = useState(() => communityCache.peek('feed')?.next_cursor || null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(() => !communityCache.peek('feed'));
  const [posting, setPosting] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerError, setComposerError] = useState('');
  const [attachment, setAttachment] = useState(null);
  const [preparing, setPreparing] = useState(false);
  const [viewer, setViewer] = useState(() => ({ ...communityViewerCache.peek(user?.uid) }));
  const [selected, setSelected] = useState(null);
  const [imageView, setImageView] = useState(null);
  const [reporting, setReporting] = useState(null);
  const [editing, setEditing] = useState(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [liking, setLiking] = useState({});
  const [notice, setNotice] = useState('');
  const dialog = useRef(null);
  const textarea = useRef(null);
  const fileInput = useRef(null);
  const pending = useRef(null);
  const alive = useRef(false);
  const busy = useRef(false);
  const actionBusy = useRef(new Set());
  const userId = user?.uid;
  const postIds = posts.map(post => post.id).join(',');
  const hasDraftImage = !!attachment || (editing?.has_image && !removeImage);
  const selectedId = selected?.id;

  useEffect(() => {
    if (selectedId) window.scrollTo(0, 0);
  }, [selectedId]);

  useEffect(() => {
    const closeMenus = event => {
      document.querySelectorAll('.community-post-menu[open]').forEach(menu => {
        if (event.type === 'keydown' ? event.key === 'Escape' : !menu.contains(event.target)) menu.open = false;
      });
    };
    document.addEventListener('pointerdown', closeMenus);
    document.addEventListener('keydown', closeMenus);
    return () => {
      document.removeEventListener('pointerdown', closeMenus);
      document.removeEventListener('keydown', closeMenus);
    };
  }, []);

  useEffect(() => {
    if (!userId || !postIds) return;
    let stopped = false;
    let reading = false;
    const refresh = async () => {
      if (reading || document.hidden) return;
      reading = true;
      try {
        const states = await communityViewerCache.read(userId, postIds.split(','), loadCommunityViewer);
        if (!stopped) setViewer({ ...states });
      } catch (failure) {
        if (!stopped && failure.message === 'LOGIN_REQUIRED') setViewer({});
      } finally { reading = false; }
    };
    void refresh();
    const timer = setInterval(refresh, 30000);
    return () => { stopped = true; clearInterval(timer); };
  }, [postIds, userId]);

  const updatePost = useCallback(change => {
    const update = list => list.map(post => post.id === change.id ? { ...post, ...change } : post);
    const cached = communityCache.peek('feed');
    if (cached) communityCache.write('feed', { ...cached, posts: update(cached.posts) });
    const postKey = `post:${change.id}`;
    const detail = communityCache.peek(postKey);
    if (detail) communityCache.write(postKey, { ...detail, ...change });
    else communityCache.invalidate(postKey); // Discard an older in-flight read after mutation.
    if (!alive.current) return;
    setPosts(update);
    setSelected(previous => previous?.id === change.id ? { ...previous, ...change } : previous);
  }, []);

  const like = async post => {
    if (actionBusy.current.has(post.id)) return;
    actionBusy.current.add(post.id); setLiking(previous => ({ ...previous, [post.id]: true }));
    const cacheOwner = communityViewerCache.peek(userId);
    try {
      const result = await likeCommunityPost(post.id, !viewer[post.id]?.liked);
      updatePost({ id: post.id, like_count: result.like_count });
      // Do not retain a late mutation after logout/account switch.
      communityViewerCache.write(userId, post.id, { liked: result.liked }, cacheOwner);
      // Activity can hide this still-mounted component during the request.
      // Keep its confirmed reaction state ready for the next reveal.
      setViewer(previous => ({ ...previous, [post.id]: { ...previous[post.id], liked: result.liked } }));
    } catch (failure) { if (alive.current) setError(communityError(failure)); }
    finally { actionBusy.current.delete(post.id); setLiking(previous => ({ ...previous, [post.id]: false })); }
  };

  const edit = async post => {
    try {
      const fresh = await getCommunityPost(post.id);
      if (!alive.current) return;
      setEditing(fresh); setContent(fresh.content); setAttachment(null); setRemoveImage(false);
      setComposerError(''); pending.current = null; setComposerOpen(true);
    } catch (failure) { if (alive.current) setError(communityError(failure)); }
  };

  const remove = async post => {
    if (!window.confirm('ลบโพสต์นี้? โพสต์และรูปจะไม่แสดงใน Community อีก')) return;
    if (actionBusy.current.has(post.id)) return;
    actionBusy.current.add(post.id);
    try {
      await deleteCommunityPost(post.id);
      communityCommentCache.invalidate(post.id);
      communityCache.invalidate(`post:${post.id}`);
      communityCache.invalidate('feed');
      if (alive.current) { setPosts(previous => previous.filter(item => item.id !== post.id)); setSelected(null); }
    } catch (failure) { if (alive.current) setError(communityError(failure)); }
    finally { actionBusy.current.delete(post.id); }
  };

  useEffect(() => {
    if (!composerOpen) return;
    const element = dialog.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    element.showModal();
    textarea.current?.focus();
    return () => { element.close(); document.body.style.overflow = previousOverflow; };
  }, [composerOpen]);

  useEffect(() => {
    alive.current = true;
    let stopped = false;
    let refreshing = false;
    const refreshOwner = {};
    const refresh = async () => {
      if (refreshing || busy.current || document.hidden) return;
      refreshing = true;
      busy.current = refreshOwner;
      try {
        const result = await communityCache.read('feed', loadCommunity);
        if (!stopped) { setPosts(result.posts); setCursor(result.next_cursor); setError(''); }
      } catch (failure) {
        if (!stopped && failure.message !== 'CACHE_INVALIDATED') setError('โหลดโพสต์ไม่ได้ กรุณาลองใหม่อีกครั้ง');
      } finally {
        refreshing = false;
        if (busy.current === refreshOwner) busy.current = false;
        if (!stopped) setLoading(false);
      }
    };
    void refresh();
    const timer = setInterval(() => {
      if (!refreshing && !busy.current && !document.hidden) { communityCache.expire('feed'); void refresh(); }
    }, 30000);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      stopped = true; alive.current = false; clearInterval(timer);
      if (busy.current === refreshOwner) busy.current = false;
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    if (posting || preparing || (!content.trim() && !hasDraftImage)) return;
    setPosting(true); setComposerError('');
    // A lost response must not duplicate the same draft on retry.
    pending.current ??= { content: content.trim(), image: attachment?.encoded, id: crypto.randomUUID() };
    try {
      if (editing) {
        const changed = await editCommunityPost(editing.id, { content: content.trim(), expected_revision: editing.revision || 0,
          ...(attachment ? { image: attachment.encoded } : {}), remove_image: removeImage && !attachment });
        updatePost(changed);
        if (alive.current) { setContent(''); setAttachment(null); setEditing(null); setComposerOpen(false); pending.current = null; }
        return;
      }
      const post = await postCommunity(pending.current.content, pending.current.id, pending.current.image);
      const cached = communityCache.peek('feed');
      communityCache.write('feed', { posts: [post, ...(cached?.posts || []).filter(item => item.id !== post.id)],
        next_cursor: cached?.next_cursor || null });
      if (!alive.current) return;
      setPosts(previous => [post, ...previous.filter(item => item.id !== post.id)]);
      setContent(''); setAttachment(null); setComposerOpen(false); pending.current = null;
    } catch (failure) {
      if (alive.current) setComposerError(communityError(failure));
    } finally { if (alive.current) setPosting(false); }
  };

  const attach = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setPreparing(true); setComposerError('');
    try {
      const prepared = await preparePostImage(file);
      if (alive.current) { setAttachment(prepared); setRemoveImage(false); pending.current = null; }
    } catch (failure) { if (alive.current) setComposerError(failure.message); }
    finally { if (alive.current) setPreparing(false); }
  };

  const more = async () => {
    if (!cursor || busy.current) return;
    busy.current = true; setLoading(true);
    try {
      const result = await loadCommunity(cursor);
      if (alive.current) {
        setPosts(previous => [...previous, ...result.posts.filter(post => !previous.some(item => item.id === post.id))]);
        setCursor(result.next_cursor); setError('');
      }
    } catch { if (alive.current) setError('โหลดโพสต์เพิ่มเติมไม่ได้'); }
    finally { busy.current = false; if (alive.current) setLoading(false); }
  };

  return (
    <section id="social-page"><div className="section-content">
      {!selected && <div className="scanner-header"><h2>Community</h2></div>}
      {!selected && <button className="community-compose-trigger" type="button" aria-haspopup="dialog" aria-label="สร้างโพสต์"
        onClick={() => { setEditing(null); setRemoveImage(false); setContent(''); setAttachment(null); pending.current = null;
          setComposerError(''); setComposerOpen(true); }}>
        <span className="community-compose-placeholder">มีอะไรน่าสงสัย? โพสต์ถามเลย...</span>
        <span className="community-compose-plus" aria-hidden="true">+</span>
      </button>}
      <dialog ref={dialog} className="community-composer" aria-labelledby="community-composer-title"
        onCancel={event => { event.preventDefault(); if (!posting && !preparing) setComposerOpen(false); }}>
        <form onSubmit={submit}>
          <div className="community-composer-header">
            <button type="button" className="community-close" aria-label="ปิดหน้าสร้างโพสต์"
              disabled={posting || preparing} onClick={() => setComposerOpen(false)}>×</button>
            <h3 id="community-composer-title">{editing ? 'แก้ไขโพสต์' : 'สร้างโพสต์'}</h3>
            <button className="community-submit" type="submit"
              disabled={posting || preparing || (!content.trim() && !hasDraftImage)}>
              {posting ? 'กำลังส่ง...' : editing ? 'บันทึก' : 'โพสต์'}
            </button>
          </div>
          <textarea ref={textarea} aria-label="ข้อความโพสต์" maxLength={2000} value={content}
            disabled={posting || preparing} placeholder="อยากแชร์อะไรกับชุมชน?"
            onChange={event => { setContent(event.target.value); pending.current = null; }} />
          {hasDraftImage && <div className="community-image-preview">
            <img src={attachment?.preview || getCommunityImageUrl(editing)} alt="ตัวอย่างภาพก่อนโพสต์" />
            <button type="button" disabled={posting || preparing} aria-label="เอาภาพออก"
              onClick={() => { setAttachment(null); setRemoveImage(true); pending.current = null; }}>×</button>
          </div>}
          <div className="community-composer-tools">
            <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={attach} />
            <button type="button" className="community-attach" disabled={posting || preparing}
              onClick={() => fileInput.current.click()}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                <rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8" cy="8" r="1.5" />
                <path d="m3 17 5-5 4 4 4-6 5 7" />
              </svg>
              {preparing ? 'กำลังเตรียมภาพ...' : hasDraftImage ? 'เปลี่ยนภาพ' : 'แนบภาพ'}
            </button>
            <span>{content.length}/2000 · สาธารณะ</span>
          </div>
          {composerError && <p className="community-composer-error" role="alert">{composerError}</p>}
        </form>
      </dialog>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {selected && <CommunityPostDetail key={selected.id} post={selected} viewer={viewer[selected.id]}
        liking={liking[selected.id] || (!!userId && !viewer[selected.id])} onLike={like} onBack={() => setSelected(null)} onUpdate={updatePost}
        onImage={setImageView} onEdit={edit} onDelete={remove} onReport={setReporting} />}
      <Activity mode={selected ? 'hidden' : 'visible'}>
        {loading && <p role="status" className="page-loading">กำลังโหลดโพสต์...</p>}
        {!loading && !error && posts.length === 0 && !cursor && <p className="page-loading">ยังไม่มีโพสต์</p>}
        <CommunityFeed>{posts.map(post => <CommunityPostCard key={post.id} post={post}
          viewer={viewer[post.id]} liking={liking[post.id] || (!!userId && !viewer[post.id])} onLike={like} onOpen={setSelected}
          onImage={setImageView} onEdit={edit} onDelete={remove} onReport={setReporting} />)}</CommunityFeed>
        {cursor && <button onClick={more} disabled={loading}>ดูโพสต์เพิ่มเติม</button>}
      </Activity>
      {imageView && <CommunityImageViewer src={imageView} onClose={() => setImageView(null)} />}
      {reporting && <CommunityReportDialog post={reporting} onClose={() => setReporting(null)}
        onSaved={() => { setReporting(null); setNotice('บันทึกรายงานแล้ว รอการตรวจสอบ'); }} />}
    </div></section>
  );
};

export default Social;
