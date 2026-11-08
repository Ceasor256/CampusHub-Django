"""
Image upload processing.

Uploads are decoded with Pillow (so only real JPEG/PNG/WebP images pass),
auto-rotated, downscaled to save students' data, and re-encoded as WebP.
Re-encoding also strips EXIF metadata such as GPS location.
"""

from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from core.utils import invalid

MAX_BYTES = 6 * 1024 * 1024
MAX_COUNT = 6
MAX_SIDE = 1600
ALLOWED = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO = multi-picture JPEG from some phones

Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs


def process_image(upload) -> ContentFile:
    name = (upload.name or "photo")[:40]
    if upload.size > MAX_BYTES:
        raise invalid(f'"{name}" is larger than 6 MB.')
    try:
        img = Image.open(upload)
        if img.format not in ALLOWED:
            raise invalid(f'"{name}" isn\'t a JPG, PNG or WebP image.')
        img = ImageOps.exif_transpose(img)
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        out = BytesIO()
        img.save(out, "WEBP", quality=82, method=4)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise invalid(f'"{name}" isn\'t a valid image.')
    return ContentFile(out.getvalue(), name="photo.webp")


def process_images(files, already=0):
    files = [f for f in files if f and f.size]
    if len(files) + already > MAX_COUNT:
        raise invalid(f"You can add up to {MAX_COUNT} photos.")
    return [process_image(f) for f in files]
