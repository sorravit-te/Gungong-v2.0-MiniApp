import React, { useState } from 'react';

const Social = ({ userProfile }) => {
  const [showPopup, setShowPopup] = useState(false);

  const toggleSocialPopup = () => {
    setShowPopup(!showPopup);
  };

  const handlePostAction = (type) => {
    setShowPopup(false);
    if (window.Swal) {
      window.Swal.fire({
        icon: 'info',
        title: type === 'image' ? 'อัปโหลดรูปภาพ' : 'แนบลิงก์ URL',
        text: 'ฟังก์ชันนี้กำลังพัฒนา',
        confirmButtonColor: '#3ACE00',
      });
    }
  };

  const posts = [
    {
      id: 1,
      author: 'Somsak K.',
      time: '10 นาทีที่แล้ว',
      content: 'ช่วยดูหน่อยครับ อันนี้ลิงก์จริงหรือปลอม? มี SMS ส่งมาบอกว่าได้รับเงินคืนภาษี',
      image: '/img/scam1.png',
      likes: 12,
      comments: 4,
      type: 'warning' // เพิ่ม type เพื่อกำหนดสีเส้นด้านข้าง
    },
    {
      id: 2,
      author: 'Manee_Ja',
      time: '1 ชั่วโมงที่แล้ว',
      content: 'เตือนภัยค่ะ! 🚨 เบอร์ 02-xxx-xxxx โทรมาอ้างว่าเป็นเจ้าหน้าที่จาก DHL บอกมีพัสดุตกค้าง อย่าหลงเชื่อนะคะ',
      likes: 45,
      comments: 8,
      type: 'danger'
    },
    {
      id: 3,
      author: 'Chai_Dev',
      time: '3 ชั่วโมงที่แล้ว',
      content: 'เจอเว็บนี้ยิงโฆษณาในเฟสบุ๊คครับ อ้างว่าลงทุนได้กำไร 100% ภายใน 5 นาที ระวังกันด้วยนะครับ',
      image: '/img/scam2.png',
      likes: 89,
      comments: 21,
      type: 'warning'
    },
  ];

  return (
    <section id="social-page">
      <div className="section-content">
        <div className="scanner-header">
          <h2>My Community</h2>
        </div>

        <div className="history-controls">
          <div className="search-box">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
            </svg>
            <input type="text" placeholder="มีอะไรน่าสงสัย? โพสต์ถามเลย..." />
          </div>
          <button className="filter-btn add-post-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>
        </div>

        <div className="social-feed">
          {posts.map((post, index) => (
            <div
              key={post.id}
              className={`social-card ${post.type} animate-card`}
              style={{ animationDelay: `${0.1 + index * 0.08}s` }}
            >
              <div className="s-card-content">
                <div className="s-card-top">
                  <div className="author-info">
                    <div className="author-avatar-svg">
                      <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                      </svg>
                    </div>
                    <div className="author-details">
                      <span className="author-name">{post.author}</span>
                      <span className="post-time">{post.time}</span>
                    </div>
                  </div>
                  <button className="more-btn">⋮</button>
                </div>

                <div className="s-card-main">
                  <div className="s-text-group">
                    <p className="post-text">{post.content}</p>
                    {post.image && (
                      <img src={post.image} alt="Post" className="post-image" />
                    )}
                  </div>
                </div>

                <div className="s-card-bottom">
                  <div className="action-group">
                    <button className="social-action-btn">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                      </svg>
                      {post.likes}
                    </button>
                    <button className="social-action-btn">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                      </svg>
                      {post.comments}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Social;