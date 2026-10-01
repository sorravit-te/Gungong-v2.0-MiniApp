import { useEffect, useRef, useState } from 'react';
import { getCommunityImageUrl, loadCommunity, postCommunity } from '../utils/community';
import { preparePostImage } from '../utils/communityImage';

const Social = () => {
  const [posts, setPosts] = useState([]);
  const [content, setContent] = useState('');
  const [cursor, setCursor] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [composerError, setComposerError] = useState('');
  const [attachment, setAttachment] = useState(null);
  const [preparing, setPreparing] = useState(false);
  const dialog = useRef(null);
  const textarea = useRef(null);
  const fileInput = useRef(null);
  const pending = useRef(null);
  const alive = useRef(false);
  const busy = useRef(false);

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
    const refresh = async () => {
      if (busy.current || document.hidden) return;
      busy.current = true;
      try {
        const result = await loadCommunity();
        if (!stopped) { setPosts(result.posts); setCursor(result.next_cursor); setError(''); }
      } catch {
        if (!stopped) setError('โหลดโพสต์ไม่ได้ กรุณาลองใหม่อีกครั้ง');
      } finally { busy.current = false; if (!stopped) setLoading(false); }
    };
    void refresh();
    const timer = setInterval(refresh, 30000);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      stopped = true; alive.current = false; clearInterval(timer);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    if (posting || preparing || (!content.trim() && !attachment)) return;
    setPosting(true); setComposerError('');
    // A lost response must not duplicate the same draft on retry.
    pending.current ??= { content: content.trim(), image: attachment?.encoded, id: crypto.randomUUID() };
    try {
      const post = await postCommunity(pending.current.content, pending.current.id, pending.current.image);
      if (!alive.current) return;
      setPosts(previous => [post, ...previous.filter(item => item.id !== post.id)]);
      setContent(''); setAttachment(null); setComposerOpen(false); pending.current = null;
    } catch (failure) {
      if (alive.current) setComposerError(failure.message === 'LOGIN_REQUIRED'
        ? 'กรุณาเข้าสู่ระบบ LINE หรือ Google ก่อนโพสต์'
        : 'ยังยืนยันการโพสต์ไม่ได้ กรุณารีเฟรชเพื่อตรวจสอบ หรือกดส่งซ้ำด้วยข้อความเดิม');
    } finally { if (alive.current) setPosting(false); }
  };

  const attach = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setPreparing(true); setComposerError('');
    try {
      const prepared = await preparePostImage(file);
      if (alive.current) { setAttachment(prepared); pending.current = null; }
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
      <div className="scanner-header"><h2>My Community</h2></div>
      <button className="community-compose-trigger" type="button" aria-haspopup="dialog"
        onClick={() => { setComposerError(''); setComposerOpen(true); }}>
        มีอะไรน่าสงสัย? โพสต์ถามเลย...
      </button>
      <dialog ref={dialog} className="community-composer" aria-labelledby="community-composer-title"
        onCancel={event => { event.preventDefault(); if (!posting && !preparing) setComposerOpen(false); }}>
        <form onSubmit={submit}>
          <div className="community-composer-header">
            <button type="button" className="community-close" aria-label="ปิดหน้าสร้างโพสต์"
              disabled={posting || preparing} onClick={() => setComposerOpen(false)}>×</button>
            <h3 id="community-composer-title">สร้างโพสต์</h3>
            <button className="community-submit" type="submit"
              disabled={posting || preparing || (!content.trim() && !attachment)}>
              {posting ? 'กำลังส่ง...' : 'โพสต์'}
            </button>
          </div>
          <textarea ref={textarea} aria-label="ข้อความโพสต์" maxLength={2000} value={content}
            disabled={posting || preparing} placeholder="อยากแชร์อะไรกับชุมชน?"
            onChange={event => { setContent(event.target.value); pending.current = null; }} />
          {attachment && <div className="community-image-preview">
            <img src={attachment.preview} alt="ตัวอย่างภาพก่อนโพสต์" />
            <button type="button" disabled={posting || preparing} aria-label="เอาภาพออก"
              onClick={() => { setAttachment(null); pending.current = null; }}>×</button>
          </div>}
          <div className="community-composer-tools">
            <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={attach} />
            <button type="button" className="community-attach" disabled={posting || preparing}
              onClick={() => fileInput.current.click()}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                <rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8" cy="8" r="1.5" />
                <path d="m3 17 5-5 4 4 4-6 5 7" />
              </svg>
              {preparing ? 'กำลังเตรียมภาพ...' : attachment ? 'เปลี่ยนภาพ' : 'แนบภาพ'}
            </button>
            <span>{content.length}/2000 · สาธารณะ</span>
          </div>
          {composerError && <p className="community-composer-error" role="alert">{composerError}</p>}
        </form>
      </dialog>
      {error && <p role="alert">{error}</p>}
      {loading && <p role="status">กำลังโหลดโพสต์...</p>}
      <div className="social-feed">
        {posts.map(post => <article key={post.id} className="social-card warning">
          <div className="s-card-content">
            <div className="s-card-top"><div className="author-details">
              <span className="author-name">{post.author}</span>
              <span className="post-time">{post.created_at ? new Date(post.created_at).toLocaleString('th-TH') : ''}</span>
            </div></div>
            <div className="s-card-main"><p className="post-text">{post.content}</p></div>
            {getCommunityImageUrl(post) && <img className="post-image" loading="lazy"
              src={getCommunityImageUrl(post)} alt="ภาพแนบในโพสต์" />}
          </div>
        </article>)}
      </div>
      {cursor && <button onClick={more} disabled={loading}>ดูโพสต์เพิ่มเติม</button>}
    </div></section>
  );
};

export default Social;
