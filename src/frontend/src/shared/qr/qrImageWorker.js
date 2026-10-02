import { decodeQrPixels } from './qrImagePixels.js';

self.onmessage = event => {
    try {
        const { data, width, height } = event.data;
        self.postMessage({ value: decodeQrPixels(data, width, height) });
    } catch {
        self.postMessage({ error: 'QR_IMAGE_INVALID' });
    }
};
