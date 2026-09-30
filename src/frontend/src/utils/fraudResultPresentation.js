const GUNGONG_GREEN = '#3ACE00';

export function getFraudResultPresentation(result = {}) {
    const verdict = result.verification_verdict;
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

    return {
        isSafe,
        isRisk,
        isIncomplete,
        isInvalid,
        status,
        statusColor: isSafe ? GUNGONG_GREEN : isRisk ? '#E53935' : '#D97706',
        icon: isSafe ? 'success' : isRisk || isIncomplete ? 'warning' : 'info',
        showConfidence: !verdict,
    };
}
