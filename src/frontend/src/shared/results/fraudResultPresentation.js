const GUNGONG_GREEN = '#3ACE00';

export function getHistoryResultPresentation(item = {}) {
    const urlCheck = item.url_check_result ?? {};
    const isUrl = ['link', 'qr'].includes(item.type) || Boolean(urlCheck.verification_verdict);
    const fallback = isUrl ? {
        VERIFICATION_INCOMPLETE: 'INCOMPLETE', INVALID_URL: 'INVALID',
        SUSPICIOUS_URL: 'SUSPICIOUS', SCAM_MALICIOUS: 'MALICIOUS',
    }[item.classification] : undefined;
    const presentation = getFraudResultPresentation({
        ...item, category: item.classification, reason_th: item.reason,
        url_check: urlCheck,
        verification_verdict: urlCheck.verification_verdict ?? fallback,
    });
    return { ...presentation, showConfidence: !isUrl && presentation.showConfidence };
}

function getSystemExplanation(verdict, checks) {
    if (verdict === 'INCOMPLETE') {
        const stageNames = {
            redirect: 'URL และปลายทาง', content: 'เนื้อหาหน้าเว็บ',
            local_reputation: 'ข้อมูลเฝ้าระวังในระบบ', gemini: 'การวิเคราะห์จาก AI',
            risk_history: 'หลักฐานเสี่ยงล่าสุด', external_reputation: 'ฐานข้อมูลภัยคุกคามภายนอก',
        };
        const missing = Object.entries(stageNames)
            .filter(([stage]) => checks[stage]?.required === true && checks[stage].complete !== true)
            .map(([, name]) => name);
        return `ยังตรวจสอบลิงก์ได้ไม่ครบ${missing.length ? ` ส่วนที่ยังไม่ครบ: ${missing.join(', ')}` : ''} จึงยังไม่สามารถยืนยันความปลอดภัยของลิงก์นี้ได้ ทั้งนี้การตรวจไม่ครบไม่ได้หมายความว่าพบอันตราย`;
    }
    if (verdict === 'INVALID') {
        return 'URL ไม่ถูกต้อง ไม่รองรับ หรือปลายทางไม่ผ่านเงื่อนไขความปลอดภัย จึงไม่สามารถตรวจสอบลิงก์นี้ต่อได้';
    }
    if (verdict === 'MALICIOUS' || verdict === 'SUSPICIOUS') {
        if (verdict === 'SUSPICIOUS' && checks.risk_history?.status === 'suspicious') {
            return 'มีหลักฐานแจ้งเตือนจากการตรวจครั้งก่อนที่ยังไม่หมดอายุ ผลปกติบางส่วนในครั้งนี้ยังไม่เพียงพอที่จะลบล้างคำเตือน ไม่ใช่การยืนยันว่าเว็บไซต์อันตรายแน่นอน';
        }
        if (verdict === 'SUSPICIOUS' && checks.virustotal?.reason === 'single_engine_detection') {
            return 'VirusTotal มี 1 scanner รายงานว่าอันตราย ระบบจึงแจ้งให้ระวังและตรวจสอบเพิ่มเติม ไม่ใช่การยืนยันว่าเว็บไซต์อันตรายแน่นอน';
        }
        return verdict === 'MALICIOUS'
            ? 'ผลตรวจพบหลักฐานอันตรายของลิงก์นี้ ควรหลีกเลี่ยงการเปิดลิงก์และการกรอกข้อมูลส่วนตัว'
            : 'ผลตรวจพบสัญญาณน่าสงสัยของลิงก์นี้ ควรระวังและตรวจสอบแหล่งที่มาก่อนเปิดหรือกรอกข้อมูล';
    }
    if (verdict === 'NO_THREAT_FOUND') {
        const trustedCore = checks.route?.status === 'FAST_SAFE'
            && checks.redirect?.status === 'clean' && checks.redirect.complete === true
            && checks.content?.status === 'clean' && checks.content.complete === true
            && checks.content.evidence_sufficient === true
            && ['clean', 'not_listed'].includes(checks.local_reputation?.status)
            && checks.local_reputation.complete === true
            && checks.gemini?.status === 'skipped_not_needed';
        const explanation = trustedCore
            ? 'ปลายทางผ่านเกณฑ์โดเมนที่เชื่อถือร่วมกับหลักฐานหน้าเว็บและการตรวจข้อมูลในระบบ ไม่พบสัญญาณน่าสงสัย จึงไม่จำเป็นต้องเรียก AI'
            : 'ผลการตรวจครั้งนี้ไม่พบสัญญาณอันตรายจากแหล่งข้อมูลที่ตรวจสอบ ไม่ใช่การรับประกันความปลอดภัยของลิงก์';
        return explanation + (checks.content?.content_truncated === true
            ? ' โดยตรวจเฉพาะเนื้อหาที่อ่านได้ภายในขีดจำกัด ไม่ได้ตรวจเนื้อหาทั้งหน้า' : '');
    }
    return 'ยังไม่สามารถสรุปผลการตรวจสอบลิงก์นี้ได้จากข้อมูลที่ได้รับ';
}

export function getFraudResultPresentation(result = {}) {
    const verdict = result.verification_verdict ?? result.url_check?.verification_verdict;
    const isIncomplete = verdict === 'INCOMPLETE';
    const isInvalid = verdict === 'INVALID';
    const isSafe = verdict ? verdict === 'NO_THREAT_FOUND' : result.is_safe === true;
    const isRisk = verdict
        ? ['MALICIOUS', 'SUSPICIOUS'].includes(verdict)
        : result.is_fraud === true;
    const status = isSafe
        ? 'ไม่พบสัญญาณอันตรายจากการตรวจสอบ'
        : isIncomplete
            ? 'ตรวจสอบได้ไม่ครบ'
            : isInvalid
                ? 'ลิงก์ไม่ถูกต้องหรือไม่อนุญาต'
                : isRisk ? 'มีความเสี่ยง' : 'ไม่สามารถระบุได้';

    const checks = result.checks ?? result.url_check?.checks ?? {};
    const gemini = checks.gemini;
    // Preserve the aggregate verdict; only explain completed, consistent AI evidence.
    const expectedAssessment = {
        NO_THREAT_FOUND: 'clean',
        SUSPICIOUS: 'suspicious',
        MALICIOUS: 'malicious',
    }[verdict];
    const analysisReason = expectedAssessment && gemini?.status === expectedAssessment
        && gemini.complete === true && typeof gemini.reason_th === 'string'
        && /[ก-๙]/u.test(gemini.reason_th)
        && (verdict !== 'NO_THREAT_FOUND' || gemini.evidence_sufficient === true)
        ? gemini.reason_th.trim() : '';

    return {
        isSafe,
        isRisk,
        isIncomplete,
        isInvalid,
        status,
        statusColor: isSafe ? GUNGONG_GREEN : isRisk ? '#E53935' : '#D97706',
        icon: isSafe ? 'success' : isRisk ? 'warning' : 'info',
        showConfidence: false,
        analysisReason: analysisReason !== result.reason_th?.trim?.() ? analysisReason : '',
        explanation: verdict ? analysisReason || getSystemExplanation(verdict, checks) : '',
        explanationLabel: analysisReason ? 'คำอธิบายการตรวจสอบ (AI)' : 'คำอธิบายการตรวจสอบ',
    };
}
