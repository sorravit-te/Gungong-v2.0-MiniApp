"""Bounded, local QR decoding. Never fetch the decoded payload here."""

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_QR_IMAGE_BYTES = 10 * 1024 * 1024
MAX_QR_IMAGE_PIXELS = 40_000_000


class QRImageError(ValueError):
    pass


def decode_qr_image(content: bytes) -> str | None:
    if not content or len(content) > MAX_QR_IMAGE_BYTES:
        raise QRImageError("QR_IMAGE_SIZE")
    try:
        import zxingcpp
    except ImportError as exc:
        raise QRImageError("QR_READER_UNAVAILABLE") from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise QRImageError("QR_IMAGE_TYPE")
                if image.width * image.height > MAX_QR_IMAGE_PIXELS:
                    raise QRImageError("QR_IMAGE_SIZE")
                # Decode the first frame only; shrink before allocating RGBA buffers.
                image.draft("RGB", (2000, 2000))
                image.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
                image = ImageOps.exif_transpose(image).convert("RGBA")
                background = Image.new("RGBA", image.size, "white")
                background.alpha_composite(image)
                gray = background.convert("L")
                gray.thumbnail((2000, 2000), Image.Resampling.LANCZOS)
                found = zxingcpp.read_barcodes(
                    gray, formats=zxingcpp.BarcodeFormat.QRCode,
                    try_rotate=True, try_downscale=True, try_invert=True,
                )
                values = {barcode.text.strip() for barcode in found if barcode.valid and barcode.text.strip()}
                if len(values) > 1:
                    raise QRImageError("QR_IMAGE_MULTIPLE")
                value = next(iter(values), None)
                if value and len(value) > 4096:
                    raise QRImageError("QR_CONTENT_SIZE")
                return value
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise QRImageError("QR_IMAGE_INVALID") from exc
