import { SHARE_TYPES, sharePresentation } from './historyShare';

export default function SharedScanDetails({ data }) {
    const view = data.snapshot;
    const presentation = sharePresentation(view);
    return <>
        <p className={`share-verdict share-verdict-${presentation.tone}`}>{presentation.status}</p>
        <dl className="shared-scan-fields">
            <dt>ประเภท</dt><dd>{SHARE_TYPES[view.type]}</dd>
            <dt>ข้อมูลที่แชร์</dt><dd>{view.content || 'ผู้แชร์ไม่ได้แนบเนื้อหาที่ตรวจสอบ'}</dd>
            <dt>เวลาที่ตรวจสอบ</dt><dd>{view.scanned_at ? new Date(view.scanned_at).toLocaleString('th-TH') : 'ไม่ระบุ'}</dd>
        </dl>
        <p>{presentation.explanation || 'ผลนี้เป็นการประเมินจากข้อมูลที่ตรวจสอบในเวลานั้น ไม่ใช่การรับประกันความปลอดภัย'}</p>
        <p className="share-footnote">ลิงก์หมดอายุ {new Date(data.expires_at).toLocaleString('th-TH')} · แสดงเฉพาะสำเนาผลที่เจ้าของเลือกแชร์ ไม่ใช่ History ทั้งหมด</p>
    </>;
}
