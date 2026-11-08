"""
Illustrated pictures for SAMPLE listings (development data only).

Sample items have no real photos, and we never pass off stock photos as a
seller's own. Instead each sample listing gets a clearly illustrated picture
in the site's café colours, built from its category icon and marked
"Sample illustration". Real listings always use the seller's uploaded photos.
"""

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.html import escape

from core.icons import ICONS

# (background top, background bottom, blob) per category icon, all from the café palette.
TONES = {
    "laptop": ("#f3eadf", "#e6d3bd", "#d2b391"),
    "smartphone": ("#fdf8ec", "#f8ecd0", "#e9c98c"),
    "headphones": ("#faf6f1", "#e6d3bd", "#b98e64"),
    "book-open": ("#f8ecd0", "#e9c98c", "#d9ae63"),
    "shirt": ("#faf6f1", "#f3eadf", "#d2b391"),
    "sofa": ("#f3eadf", "#d2b391", "#b98e64"),
    "refrigerator": ("#fdf8ec", "#e6d3bd", "#d2b391"),
}
DEFAULT_TONE = ("#faf6f1", "#e6d3bd", "#d2b391")


def _icon_markup(name):
    nodes = ICONS.get(name) or ICONS["package"]
    parts = []
    for tag, attrs in nodes:
        attr_text = " ".join(f'{k}="{escape(v)}"' for k, v in attrs.items())
        parts.append(f"<{tag} {attr_text}/>")
    return "".join(parts)


def listing_svg(icon_name, title):
    top, bottom, blob = TONES.get(icon_name, DEFAULT_TONE)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" width="800" height="600" role="img" aria-label="Sample illustration: {escape(title)}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.4" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.45" r="0.5"><stop offset="0" stop-color="#fffdf9" stop-opacity="0.9"/><stop offset="1" stop-color="#fffdf9" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="800" height="600" fill="url(#bg)"/>
  <circle cx="640" cy="110" r="150" fill="{blob}" opacity="0.35"/>
  <circle cx="130" cy="520" r="110" fill="{blob}" opacity="0.3"/>
  <circle cx="400" cy="280" r="230" fill="url(#glow)"/>
  <ellipse cx="400" cy="470" rx="170" ry="22" fill="#4d301d" opacity="0.12"/>
  <g transform="translate(256 136) scale(12)" fill="none" stroke="#7b5233" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{_icon_markup(icon_name)}</g>
  <g transform="translate(560 540)"><rect x="0" y="0" width="216" height="36" rx="18" fill="#fffdf9" opacity="0.85"/><text x="108" y="24" text-anchor="middle" font-family="Plus Jakarta Sans, Segoe UI, sans-serif" font-size="16" font-weight="600" fill="#7d6b5e">Sample illustration</text></g>
</svg>"""


def attach_sample_images():
    """Give every sample listing without pictures an illustration. Safe to run again."""
    from marketplace.models import Listing, ListingImage

    added = 0
    for listing in Listing.objects.filter(is_sample=True, images__isnull=True).select_related("category"):
        svg = listing_svg(listing.category.icon, listing.title).encode()
        # Saved under media/listings/<id>/ like uploads, but as .svg: written straight to
        # storage, bypassing upload_to and the photo pipeline (both for real uploads only).
        name = default_storage.save(f"listings/{listing.pk}/sample.svg", ContentFile(svg))
        ListingImage.objects.create(listing=listing, image=name, sort_order=0)
        added += 1
    return added
