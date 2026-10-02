// One small raster image per post; no SVG, original metadata or external uploads.
export const MAX_POST_IMAGE_BYTES = 128 * 1024;

export function validateImageFile(file) {
    if (!file || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        throw new Error('เลือกรูป JPG, PNG หรือ WebP เท่านั้น');
    }
    if (file.size > 10 * 1024 * 1024 || !file.size) {
        throw new Error('เลือกรูปที่มีขนาดไม่เกิน 10 MB');
    }
}

export async function preparePostImage(file) {
    validateImageFile(file);
    const url = URL.createObjectURL(file);
    const image = new Image();
    let timer;
    try {
        await new Promise((resolve, reject) => {
            timer = setTimeout(() => reject(new Error('เตรียมภาพนานเกินไป กรุณาเลือกรูปอื่น')), 15000);
            image.onload = resolve;
            image.onerror = () => reject(new Error('อ่านรูปนี้ไม่ได้ กรุณาเลือกรูปอื่น'));
            image.src = url;
        });
        clearTimeout(timer);
        const canvas = document.createElement('canvas');
        for (const edge of [1600, 1200, 900]) {
            const scale = Math.min(1, edge / Math.max(image.naturalWidth, image.naturalHeight));
            canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
            canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
            const context = canvas.getContext('2d');
            context.fillStyle = '#ffffff';
            context.fillRect(0, 0, canvas.width, canvas.height);
            context.drawImage(image, 0, 0, canvas.width, canvas.height);
            for (const quality of [0.85, 0.65, 0.45]) {
                const preview = canvas.toDataURL('image/jpeg', quality);
                const encoded = preview.split(',')[1];
                const bytes = encoded.length * 3 / 4 - (encoded.endsWith('==') ? 2 : encoded.endsWith('=') ? 1 : 0);
                if (bytes <= MAX_POST_IMAGE_BYTES) return { encoded, preview };
            }
        }
        throw new Error('รูปมีรายละเอียดมากเกินไป กรุณาเลือกรูปขนาดเล็กลง');
    } finally { clearTimeout(timer); image.src = ''; URL.revokeObjectURL(url); }
}
