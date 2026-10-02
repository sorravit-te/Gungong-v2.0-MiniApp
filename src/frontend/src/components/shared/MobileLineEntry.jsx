import { useState } from 'react';
import { getMobileLineTarget } from '../../utils/lineAuth';

export default function MobileLineEntry() {
    // Capture before init consumes callback parameters. A real anchor provides
    // a user gesture if the OS blocks the automatic Universal/App Link launch.
    const [target] = useState(() => getMobileLineTarget({ sdk: window.liff,
        location: window.location, navigator: window.navigator }));
    if (!target) return null;
    return <aside className="mobile-line-entry" aria-label="เปิด LINE Mini App">
        <span>หากยังไม่เข้า LINE ให้แตะปุ่มนี้</span>
        <a href={target}>เปิดใน LINE</a>
    </aside>;
}
