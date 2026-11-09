"""
Illustrated pictures for SAMPLE listings (development data only).

Sample items have no real photos, and we never pass off stock photos as a
seller's own. Instead each sample listing gets a clearly illustrated picture
in the site's colours, built from its category icon and marked
"Sample illustration". Real listings always use the seller's uploaded photos.
"""

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.html import escape

from core.icons import ICONS

# (background top, background bottom, blob) per category icon: cream beige,
# muted sage and soft burgundy tints from the site palette.
TONES = {
    "laptop": ("#f7ede0", "#e8d2b5", "#a5a79b"),
    "smartphone": ("#f5f5f2", "#d4d5cc", "#e8d2b5"),
    "headphones": ("#fbf3f1", "#e5c0ba", "#a5a79b"),
    "book-open": ("#fcf8f2", "#efdfc9", "#cc8c84"),
    "shirt": ("#f4e2de", "#e8d2b5", "#a5a79b"),
    "sofa": ("#e9eae4", "#bdbfb4", "#e8d2b5"),
    "refrigerator": ("#f7ede0", "#d4d5cc", "#cc8c84"),
}
DEFAULT_TONE = ("#fcf8f2", "#e8d2b5", "#a5a79b")


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
  <ellipse cx="400" cy="470" rx="170" ry="22" fill="#240302" opacity="0.12"/>
  <g transform="translate(256 136) scale(12)" fill="none" stroke="#590907" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{_icon_markup(icon_name)}</g>
  <g transform="translate(560 540)"><rect x="0" y="0" width="216" height="36" rx="18" fill="#fffdf9" opacity="0.85"/><text x="108" y="24" text-anchor="middle" font-family="Plus Jakarta Sans, Segoe UI, sans-serif" font-size="16" font-weight="600" fill="#756862">Sample illustration</text></g>
</svg>"""


def attach_sample_images(refresh=False):
    """
    Give every sample listing without pictures an illustration. Safe to run again.
    refresh=True redraws existing sample illustrations (after a colour change).
    """
    from marketplace.models import Listing, ListingImage

    if refresh:
        for old in ListingImage.objects.filter(listing__is_sample=True, image__endswith="sample.svg"):
            old.image.delete(save=False)
            old.delete()
    added = 0
    for listing in Listing.objects.filter(is_sample=True, images__isnull=True).select_related("category"):
        svg = listing_svg(listing.category.icon, listing.title).encode()
        # Saved under media/listings/<id>/ like uploads, but as .svg: written straight to
        # storage, bypassing upload_to and the photo pipeline (both for real uploads only).
        name = default_storage.save(f"listings/{listing.pk}/sample.svg", ContentFile(svg))
        ListingImage.objects.create(listing=listing, image=name, sort_order=0)
        added += 1
    return added
