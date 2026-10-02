import { normalizeScannedUrl, QrScanInputError } from './qrScan.js';

export const MAX_QR_IMAGE_BYTES = 10 * 1024 * 1024;
export const QR_IMAGE_TYPES = 'image/jpeg,image/png,image/webp';

export function validateQrImage(file) {
    if (!file || !QR_IMAGE_TYPES.split(',').includes(file.type)) throw new QrScanInputError('QR_IMAGE_TYPE');
    if (!file.size || file.size > MAX_QR_IMAGE_BYTES) throw new QrScanInputError('QR_IMAGE_SIZE');
}

export function readQrImageUrl(file, { signal, timeoutMs = 15000 } = {}) {
    validateQrImage(file);
    if (signal?.aborted) return Promise.reject(new QrScanInputError('QR_SCAN_CANCELLED'));
    return new Promise((resolve, reject) => {
        let image, canvas, worker, objectUrl, timer;
        let settled = false;
        const finish = (error, value) => {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            signal?.removeEventListener('abort', cancel);
            worker?.terminate();
            if (image) { image.onload = null; image.onerror = null; image.src = ''; }
            if (canvas) { canvas.width = 0; canvas.height = 0; }
            if (objectUrl) URL.revokeObjectURL(objectUrl);
            if (error) reject(error); else resolve(value);
        };
        const cancel = () => finish(new QrScanInputError('QR_SCAN_CANCELLED'));
        signal?.addEventListener('abort', cancel, { once: true });
        timer = setTimeout(() => finish(new QrScanInputError('QR_IMAGE_TIMEOUT')), timeoutMs);
        try {
            objectUrl = URL.createObjectURL(file);
            image = new Image();
            image.onerror = () => finish(new QrScanInputError('QR_IMAGE_INVALID'));
            image.onload = () => {
                try {
                    const width = image.naturalWidth, height = image.naturalHeight;
                    if (!width || !height || width * height > 40_000_000) throw new Error('Dimensions');
                    const scale = Math.min(1, 2000 / Math.max(width, height));
                    canvas = document.createElement('canvas');
                    canvas.width = Math.max(1, Math.round(width * scale));
                    canvas.height = Math.max(1, Math.round(height * scale));
                    const context = canvas.getContext('2d', { willReadFrequently: true });
                    if (!context) throw new Error('Canvas');
                    context.fillStyle = '#ffffff';
                    context.fillRect(0, 0, canvas.width, canvas.height);
                    context.drawImage(image, 0, 0, canvas.width, canvas.height);
                    const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
                    worker = new Worker(new URL('./qrImageWorker.js', import.meta.url), { type: 'module' });
                    worker.onerror = () => finish(new QrScanInputError('QR_IMAGE_INVALID'));
                    worker.onmessage = event => {
                        if (event.data?.error) { finish(new QrScanInputError('QR_IMAGE_INVALID')); return; }
                        if (!event.data?.value) { finish(new QrScanInputError('QR_IMAGE_NOT_FOUND')); return; }
                        try { finish(null, normalizeScannedUrl(event.data.value)); }
                        catch (error) { finish(error); }
                    };
                    worker.postMessage({ data: pixels.data, width: canvas.width, height: canvas.height },
                        [pixels.data.buffer]);
                } catch { finish(new QrScanInputError('QR_IMAGE_INVALID')); }
            };
            image.src = objectUrl;
        } catch { finish(new QrScanInputError('QR_IMAGE_INVALID')); }
    });
}
