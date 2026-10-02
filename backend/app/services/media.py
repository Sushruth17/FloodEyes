"""Image preparation before any model call."""

import io

from PIL import Image, ImageOps

MAX_SIDE_PX = 1536


def prepare_image(data: bytes, max_side: int = MAX_SIDE_PX) -> bytes:
    """Apply EXIF orientation, downscale to max_side, re-encode as JPEG (drops EXIF)."""
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
