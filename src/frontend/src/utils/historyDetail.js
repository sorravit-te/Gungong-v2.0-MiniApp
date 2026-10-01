import { getHistoryResultPresentation } from './fraudResultPresentation.js';

const escapeHtml = (value) => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

function resultPopup(item, typeName) {
    const presentation = getHistoryResultPresentation(item);
    const isUrl = item.type === 'link' || item.type === 'qr';
    const displayText = item.message_text || item.account_number || item.phone_number || 'No content';
    const hasConfidence = presentation.showConfidence && item.confidence_score !== undefined && item.confidence_score !== null;
    return {
        title: isUrl ? presentation.status : item.is_safe ? 'ปลอดภัย ✅' : 'อันตราย! ⚠️',
        html: `
            <div style="text-align: left; font-size: 14px;">
                <p><b>ข้อความ:</b> ${escapeHtml(displayText)}</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 10px 0;">
                <p><b>ประเภท:</b> ${escapeHtml(typeName(item.type))}</p>
                ${hasConfidence ? `<p><b>ความมั่นใจ:</b> ${escapeHtml(item.confidence_score)}%</p>` : ''}
                ${item.reason ? `<p><b>เหตุผล:</b> ${escapeHtml(item.reason)}</p>` : ''}
                ${presentation.explanation ? `<p><b>คำอธิบาย:</b> ${escapeHtml(presentation.explanation)}</p>` : ''}
            </div>
        `,
        icon: presentation.icon,
        confirmButtonColor: presentation.statusColor,
        confirmButtonText: 'ปิด',
        showCloseButton: true,
    };
}

// Read only the clicked URL record. Owning the popup/request prevents a late
// response from reopening it after dismissal, navigation or another selection.
export function createHistoryDetailController({ getDetail, swal, typeName, timeoutMs = 12000 }) {
    let active = null;
    let disposed = false;

    function cancel(request) {
        if (active === request) active = null;
        request.controller.abort();
    }

    return {
        async open(item) {
            if (disposed) return;
            if (active) cancel(active);
            if (!['link', 'qr'].includes(item.type)) {
                swal.fire(resultPopup(item, typeName));
                return;
            }
            const request = { controller: new AbortController() };
            active = request;
            let timer;
            swal.fire({
                title: 'กำลังโหลดรายละเอียดประวัติ',
                allowOutsideClick: false,
                showConfirmButton: false,
                showCloseButton: true,
                didOpen: () => swal.showLoading(),
                willClose: () => { if (active === request) cancel(request); },
                didDestroy: () => { if (active === request) cancel(request); },
            });
            try {
                if (typeof item.id !== 'string' || !item.id) throw new Error('INVALID_HISTORY');
                const cancellation = new Promise((_, reject) => {
                    request.controller.signal.addEventListener('abort', () => reject(new Error('HISTORY_CANCELLED')), { once: true });
                    timer = setTimeout(() => {
                        reject(new Error('HISTORY_TIMEOUT'));
                        request.controller.abort();
                    }, timeoutMs);
                });
                const detail = await Promise.race([
                    getDetail(item.id, { signal: request.controller.signal }), cancellation,
                ]);
                if (disposed || active !== request) return;
                if (!detail || Array.isArray(detail) || detail.id !== item.id
                    || detail.type !== item.type || typeof detail.message_text !== 'string') {
                    throw new Error('INVALID_HISTORY');
                }
                active = null;
                swal.fire(resultPopup(detail, typeName));
            } catch (error) {
                if (disposed || active !== request) return;
                active = null;
                swal.fire({
                    icon: 'error', title: 'ไม่สามารถโหลดรายละเอียดประวัติได้',
                    text: error.message === 'HISTORY_TIMEOUT'
                        ? 'การโหลดใช้เวลานานเกินกำหนด กรุณาลองใหม่อีกครั้ง'
                        : error.status === 404 ? 'ไม่พบรายการประวัตินี้ อาจถูกลบแล้ว'
                            : 'กรุณาลองใหม่อีกครั้ง โดยระบบไม่ได้ตรวจลิงก์ซ้ำ',
                    confirmButtonText: 'ปิด', confirmButtonColor: '#3ACE00',
                });
            } finally {
                clearTimeout(timer);
            }
        },
        dispose() {
            disposed = true;
            if (active) {
                cancel(active);
                swal.close();
            }
        },
    };
}
