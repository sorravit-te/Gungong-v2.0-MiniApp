"""Small public post images; decode/re-encode, strip metadata, never fetch URLs."""
import base64
import binascii
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 128 * 1024
MAX_IMAGE_BASE64 = ((MAX_IMAGE_BYTES + 2) // 3) * 4
MAX_IMAGE_PIXELS = 1600 * 1600


def normalize_post_image(encoded: str | None) -> bytes | None:
    if encoded is None:
        return None
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("Image too large")
        with Image.open(BytesIO(raw)) as source:
            if (source.format not in {"JPEG", "PNG", "WEBP"}
                    or source.width * source.height > MAX_IMAGE_PIXELS
                    or getattr(source, "n_frames", 1) != 1):
                raise ValueError("Unsupported image")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1600, 1600))
            # A fresh image carries no EXIF, GPS, comments or original metadata.
            clean = Image.new("RGB", image.size)
            clean.paste(image)
            for quality in (85, 70, 55, 40):
                output = BytesIO()
                clean.save(output, format="JPEG", quality=quality, optimize=True)
                if output.tell() <= MAX_IMAGE_BYTES:
                    return output.getvalue()
            raise ValueError("Image too large")
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("Invalid image") from error
