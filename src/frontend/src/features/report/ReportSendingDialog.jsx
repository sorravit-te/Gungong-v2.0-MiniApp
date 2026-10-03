import { useLayoutEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

export default function ReportSendingDialog() {
  const dialog = useRef(null);

  useLayoutEffect(() => {
    const element = dialog.current;
    const previousOverflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = 'hidden';
    return () => {
      element.close();
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  // The native modal keeps focus and taps inside the popup, even on mobile.
  // A portal avoids the page transition's transform clipping the overlay.
  return createPortal(
    <dialog ref={dialog} className="report-sending-dialog" tabIndex={-1}
      aria-labelledby="report-sending-title" aria-describedby="report-sending-description"
      onCancel={event => event.preventDefault()}>
      <span className="report-sending-spinner" aria-hidden="true" />
      <h3 id="report-sending-title">กำลังส่งเบาะแส</h3>
      <p id="report-sending-description" role="status">กรุณารอสักครู่ กำลังบันทึกข้อมูลของคุณ</p>
    </dialog>, document.body,
  );
}
