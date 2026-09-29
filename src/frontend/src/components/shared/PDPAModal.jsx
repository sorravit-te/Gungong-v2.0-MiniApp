import React, { useState, useRef, useEffect } from 'react';

const PDPAModal = ({ isOpen, onAccept }) => {
  const [canCheck, setCanCheck] = useState(true); // Temporarily disabled scroll requirement
  const [isChecked, setIsChecked] = useState(false);
  const scrollAreaRef = useRef(null);

  useEffect(() => {
    const scrollArea = scrollAreaRef.current;
    if (scrollArea) {
      // Check if content is scrollable
      if (scrollArea.scrollHeight <= scrollArea.clientHeight) {
        setCanCheck(true);
      }
    }
  }, [isOpen]);

  const handleScroll = () => {
    const scrollArea = scrollAreaRef.current;
    if (scrollArea) {
      const scrolledToBottom =
        scrollArea.scrollHeight - scrollArea.scrollTop <= scrollArea.clientHeight + 10;
      if (scrolledToBottom) {
        setCanCheck(true);
      }
    }
  };

  const handleAccept = () => {
    if (isChecked) {
      localStorage.setItem('gungong_pdpa_accepted', 'true');
      onAccept();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="pdpa-overlay" style={{ display: 'flex' }}>
      <div className="pdpa-box">
        <div className="pdpa-header">
          <div className="pdpa-icon">
            <img src="/img/notice.png" alt="Notice Icon" />
          </div>
          <h2>ข้อตกลงและนโยบายข้อมูลส่วนบุคคล</h2>
        </div>

        <div
          className="pdpa-scroll-area"
          ref={scrollAreaRef}
          onScroll={handleScroll}
        >
          <p><strong>ข้าพเจ้ารับทราบและตระหนักดีว่า</strong>
            ในการใช้บริการระบบปัญญาประดิษฐ์เพื่อตรวจสอบและป้องกันการฉ้อโกง ของ GUNGONG MINI APP นั้น
            มีความจำเป็นอย่างยิ่งที่ผู้ให้บริการต้องเก็บรวบรวมข้อมูลส่วนบุคคลและข้อมูลพฤติกรรมการใช้งานของข้าพเจ้า
            เพื่อความปลอดภัยสูงสุดในการทำธุรกรรม</p>
          <p>ในการนี้ ข้าพเจ้าขอแสดงเจตนาตกลงและให้ความยินยอม แก่ผู้ให้บริการในการเก็บรวบรวม ใช้
            และเปิดเผยข้อมูลของข้าพเจ้า อันได้แก่ ข้อมูลประวัติการทำรายการ รหัสระบุตัวตนของอุปกรณ์อิเล็กทรอนิกส์
            หมายเลขระบุตำแหน่งคอมพิวเตอร์ และรูปแบบพฤติกรรมการใช้งาน เพื่อนำไปใช้ในการวิเคราะห์ความเสี่ยง
            และข้าพเจ้ายินยอมเป็นพิเศษให้ผู้ให้บริการนำข้อมูลดังกล่าวไปใช้ในกระบวนการ เรียนรู้และฝึกสอนระบบปัญญาประดิษฐ์
            ให้มีความแม่นยำและฉลาดขึ้นในการตรวจจับรูปแบบการทุจริตใหม่ๆ</p>
          <p>ข้าพเจ้ายินยอมให้ผู้ให้บริการนำผลลัพธ์จากการวิเคราะห์
            หรือข้อมูลที่ผ่านกระบวนการทำให้ไม่สามารถระบุตัวตนของข้าพเจ้าได้แล้ว ไปใช้เพื่อประโยชน์ในทางธุรกิจและ
            การสร้างรายได้ในรูปแบบการให้บริการระบบเชื่อมต่อข้อมูลทางเทคนิค แก่บุคคลภายนอก องค์กรอื่น หรือสถาบันการเงิน
            เพื่อใช้เป็นฐานข้อมูลกลางในการประเมินคะแนนความเสี่ยง ซึ่งถือเป็นการช่วยยกระดับความปลอดภัยของระบบเศรษฐกิจโดยรวม
            โดยข้าพเจ้ายอมรับให้ข้อมูลของข้าพเจ้าเป็นส่วนหนึ่งของชุดข้อมูลในการให้บริการดังกล่าว</p>
          <p>นอกจากนี้ ข้าพเจ้ายินยอมให้ผู้ให้บริการนำข้อมูลของข้าพเจ้าไปรวบรวมและประมวลผลเพื่อจัดทำ
            รายงานสรุปสถิติในภาพรวม ผลการวิจัยแนวโน้มตลาด หรือบทวิเคราะห์ความเสี่ยง เพื่อการเผยแพร่ แบ่งปัน
            หรือจำหน่ายให้แก่สาธารณชนหรือหน่วยงานภายนอก โดยข้อมูลในส่วนนี้จะเป็นข้อมูลภาพรวมที่ไม่เจาะจงตัวบุคคล</p>
          <p>ท้ายที่สุด ข้าพเจ้ายินยอมให้ผู้ให้บริการใช้ข้อมูลและผลการวิเคราะห์ดังกล่าว เพื่อวัตถุประสงค์ทาง
            การตลาดและการส่งเสริมการขาย รวมถึงการส่งต่อข้อมูลให้แก่พันธมิตรทางธุรกิจที่ได้รับการคัดเลือก เพื่อนำเสนอสินค้า
            บริการ หรือสิทธิประโยชน์ที่เกี่ยวข้องและเหมาะสมกับข้าพเจ้า
            ข้าพเจ้ารับทราบว่าข้าพเจ้ามีสิทธิในการขอยกเลิกความยินยอมนี้ได้ในภายหลัง ผ่านช่องทางที่ผู้ให้บริการกำหนดไว้</p>

          <div style={{ marginTop: '20px', textAlign: 'center', borderTop: '1px dashed #eee', paddingTop: '15px' }}>
            <a
              href="https://www.ratchakitcha.soc.go.th/DATA/PDF/2562/A/069/T_0052.PDF"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#3ACE00', textDecoration: 'none', fontSize: '13px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '5px' }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
              อ่านฉบับเต็ม: พระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล พ.ศ. ๒๕๖๒
            </a>
          </div>
        </div>

        <div className="pdpa-footer">
          <div className="pdpa-consent-box">
            <input
              type="checkbox"
              id="pdpa-checkbox"
              disabled={!canCheck}
              checked={isChecked}
              onChange={(e) => setIsChecked(e.target.checked)}
            />
            <label
              htmlFor="pdpa-checkbox"
              style={{ opacity: canCheck ? 1 : 0.5, cursor: canCheck ? 'pointer' : 'not-allowed' }}
            >
              ข้าพเจ้าได้อ่านและยอมรับข้อตกลงและนโยบายข้อมูลส่วนบุคคล
            </label>
          </div>

          <button
            className="pdpa-accept-btn"
            onClick={handleAccept}
            disabled={!isChecked}
          >
            ยืนยันและดำเนินการต่อ
          </button>
        </div>
      </div>
    </div>
  );
};

export default PDPAModal;
