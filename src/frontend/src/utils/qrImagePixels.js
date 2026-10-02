import jsQR from 'jsqr';

// Decode only a bounded raster. This module runs in a worker in the application.
export function decodeQrPixels(data, width, height) {
    if (!(data instanceof Uint8ClampedArray) || !Number.isInteger(width) ||
        !Number.isInteger(height) || width < 1 || height < 1 ||
        width * height > 4_000_000 || data.length !== width * height * 4) {
        throw new Error('QR_IMAGE_INVALID');
    }
    return jsQR(data, width, height, { inversionAttempts: 'attemptBoth' })?.data ?? null;
}
