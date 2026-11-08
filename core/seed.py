"""
Seed data.

Reference data (institutions, campuses, categories) is real and safe for
production. Sample content (users @campushub.test, listings, gigs, businesses,
deals) is for development only and flagged is_sample=True.
"""

import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.models import Campus, Category, Institution

# Local development accounts. Never use these outside a dev database.
DEV_ACCOUNTS = {
    "admin": {"email": "admin@campushub.test", "password": "AdminDev2026!", "name": "CampusHub Admin"},
    "moderator": {"email": "moderator@campushub.test", "password": "ModDev2026!", "name": "Moderator Mo"},
    "student": {"email": "student@campushub.test", "password": "StudentDev2026!", "name": "Sample Student"},
}

INSTITUTIONS = [
    ("Makerere University", "MAK", "Kampala", [("Main Campus", "Wandegeya, Kampala")]),
    ("Makerere University Business School", "MUBS", "Kampala", [("Nakawa Campus", "Nakawa, Kampala")]),
    ("Kyambogo University", "KYU", "Kampala", [("Main Campus", "Kyambogo, Kampala")]),
    ("Uganda Christian University", "UCU", "Mukono", [("Mukono Campus", "Mukono")]),
    ("Kampala International University", "KIU", "Kampala", [("Kansanga Campus", "Kansanga, Kampala")]),
    ("Mbarara University of Science and Technology", "MUST", "Mbarara", [("Main Campus", "Mbarara City")]),
    ("Gulu University", "GU", "Gulu", [("Main Campus", "Laroo, Gulu")]),
]

MARKET_CATEGORIES = [
    ("phones-tablets", "Phones & tablets", "smartphone"),
    ("laptops-computers", "Laptops & computers", "laptop"),
    ("electronics", "Electronics & accessories", "headphones"),
    ("books-stationery", "Books & stationery", "book-open"),
    ("fashion", "Clothes & shoes", "shirt"),
    ("furniture-home", "Furniture & home", "sofa"),
    ("kitchen-appliances", "Kitchen & appliances", "refrigerator"),
    ("other", "Other", "package"),
]
GIG_CATEGORIES = [
    ("design", "Design & presentations", "palette"),
    ("printing-documents", "Printing & documents", "printer"),
    ("photo-video", "Photo & video", "camera"),
    ("tutoring", "Tutoring & study help", "graduation-cap"),
    ("errands-moving", "Errands & moving", "bike"),
    ("tech-repairs", "Tech support & repairs", "wrench"),
    ("events", "Event help", "calendar-days"),
    ("other", "Other", "hand-helping"),
]


@transaction.atomic
def seed_reference():
    for name, short, city, campuses in INSTITUTIONS:
        inst, _ = Institution.objects.get_or_create(slug=short.lower(), defaults={"name": name, "short_name": short, "city": city})
        for cname, area in campuses:
            Campus.objects.get_or_create(slug=f"{short.lower()}-{cname.lower().replace(' ', '-')}", defaults={"institution": inst, "name": cname, "area": area})
    for module, rows in (("marketplace", MARKET_CATEGORIES), ("gigs", GIG_CATEGORIES)):
        for i, (slug, name, icon) in enumerate(rows):
            Category.objects.get_or_create(module=module, slug=slug, defaults={"name": name, "icon": icon, "sort_order": i})


def _ago(d):
    return timezone.now() - timedelta(days=d)


def _ahead(d):
    return timezone.now() + timedelta(days=d)


@transaction.atomic
def seed_samples():
    from accounts.models import StaffRole, User
    from core.models import Report
    from deals.models import Business, Deal
    from gigs.models import Gig
    from marketplace.models import Listing
    from payments.models import Transaction

    if User.objects.filter(email=DEV_ACCOUNTS["admin"]["email"]).exists():
        return False
    camp = {c.slug: c for c in Campus.objects.all()}
    mak, kyu, mubs, ucu = camp["mak-main-campus"], camp["kyu-main-campus"], camp["mubs-nakawa-campus"], camp["ucu-mukono-campus"]
    now = timezone.now()

    def user(email, name, password, campus, **extra):
        return User.objects.create_user(
            email=email, password=password, full_name=name, campus=campus, email_verified_at=now, onboarded_at=now, last_seen_at=now, **extra
        )

    a = DEV_ACCOUNTS
    admin = user(a["admin"]["email"], a["admin"]["name"], a["admin"]["password"], mak)
    StaffRole.objects.create(user=admin, role="admin")
    mod = user(a["moderator"]["email"], a["moderator"]["name"], a["moderator"]["password"], mak)
    StaffRole.objects.create(user=mod, role="moderator")
    student = user(a["student"]["email"], a["student"]["name"], a["student"]["password"], mak, phone="+256700000001")

    # Fictional sellers with random passwords: nobody can log in as them.
    rnd = lambda: secrets.token_urlsafe(16)
    amina = user("amina.sample@campushub.test", "Amina N. (sample)", rnd(), mak, student_verified_at=now)
    brian = user("brian.sample@campushub.test", "Brian K. (sample)", rnd(), kyu)
    grace = user("grace.sample@campushub.test", "Grace A. (sample)", rnd(), mubs, student_verified_at=now)
    joel = user("joel.sample@campushub.test", "Joel M. (sample)", rnd(), ucu)
    owner = user("business.sample@campushub.test", "Patricia O. (sample)", rnd(), mak)

    mcat = {c.slug: c for c in Category.objects.filter(module="marketplace")}
    gcat = {c.slug: c for c in Category.objects.filter(module="gigs")}

    def listing(seller, campus, cat, title, price, cond, desc, age, **extra):
        obj = Listing.objects.create(seller=seller, campus=campus, category=mcat[cat], title=title, price_ugx=price, condition=cond,
                                     description=desc, is_sample=True, view_count=secrets.randbelow(120), **extra)
        Listing.objects.filter(pk=obj.pk).update(created_at=_ago(age))
        return obj

    listing(amina, mak, "laptops-computers", "HP EliteBook 840 G5 – Core i5, 8GB RAM, 256GB SSD", 1_150_000, "good", "Used for two semesters, battery holds about 4 hours. Comes with original charger. Minor scratch on the lid. Can meet at the Main Library or Wandegeya.", 1, is_negotiable=True, meetup_note="Main Library steps")
    listing(brian, kyu, "phones-tablets", "Tecno Spark 20 Pro, 256GB, dual SIM", 520_000, "like_new", "Bought in March, still has screen protector and cover. Selling because I upgraded. Box and receipt available.", 2, is_negotiable=True)
    listing(grace, mubs, "books-stationery", "Casio fx-991ES Plus scientific calculator", 45_000, "good", "Works perfectly, allowed in most exams. New battery fitted last month.", 0)
    listing(amina, mak, "books-stationery", "Engineering Mathematics – K.A. Stroud (7th edition)", 60_000, "fair", "Some highlighting in the first chapters, otherwise clean. Great for first-year engineering maths.", 3)
    listing(joel, ucu, "furniture-home", "Single mattress 4×6 (Vita Foam), 6 inch", 150_000, "good", "Clean, used for one year in a hostel. I'm moving out end of month. You collect from Mukono.", 4)
    listing(brian, kyu, "kitchen-appliances", "Hisense table-top fridge, 90L", 480_000, "good", "Cools well, quiet. Perfect for a hostel room. Can help deliver within Kyambogo area.", 5, is_negotiable=True)
    listing(grace, mubs, "fashion", "Nike Air Force 1 – size 42, white", 120_000, "like_new", "Worn twice, they're slightly small for me. Original.", 1)
    listing(amina, mak, "fashion", "Kitenge wrap dress, size M", 55_000, "new", "Tailored, never worn. Bright orange and blue print.", 6)
    listing(joel, ucu, "furniture-home", "Study desk with chair", 180_000, "good", "Solid wood desk (100×50cm) and plastic chair. Pick-up in Mukono.", 7)
    listing(brian, kyu, "electronics", "JBL Flip 5 Bluetooth speaker", 200_000, "good", "Loud and clear, charges via USB-C. Small scuff on one side.", 2)
    listing(grace, mubs, "phones-tablets", "iPhone 11, 64GB, battery 84%", 900_000, "good", "Face ID works, no cracks. Comes with cable. Serious buyers only, can meet at Nakawa campus gate.", 0, is_negotiable=True, meetup_note="MUBS main gate")
    listing(amina, mak, "kitchen-appliances", "Electric kettle 1.7L", 35_000, "good", "Boils fast, auto-off works. Selling because I got a new one.", 8)
    listing(joel, ucu, "other", "Lab coat, size L", 25_000, "like_new", "Used for one semester of chemistry practicals. Washed and ironed.", 9)
    listing(brian, kyu, "electronics", "Laptop backpack, fits 15.6 inch", 40_000, "new", "Water-resistant, with USB charging port. Black.", 3)
    sold = listing(amina, mak, "furniture-home", "Plastic drawer organiser (3 drawers)", 30_000, "good", "Shown as a sample of a completed sale.", 12, status="sold", sold_at=_ago(2))
    Transaction.objects.create(module="marketplace", reference_type="listing", reference_id=sold.pk, buyer=student, seller=amina, amount_ugx=28_000,
                               status="completed", payment_status="offline_unverified", is_sample=True, completed_at=_ago(2))

    def gig(poster, campus, cat, title, budget, mode, desc, age, deadline=None, loc=""):
        g = Gig.objects.create(poster=poster, campus=campus, category=gcat[cat], title=title, budget_ugx=budget, mode=mode, description=desc,
                               is_sample=True, deadline=_ahead(deadline) if deadline else None, location_note=loc)
        Gig.objects.filter(pk=g.pk).update(created_at=_ago(age))

    gig(grace, mubs, "design", "Design a campaign poster and 3 social media graphics", 80_000, "remote", "I'm running for the Guild council and need one A3 poster plus three square graphics for WhatsApp and Instagram. I'll share my photo and slogan. Need editable files too.", 0, 5)
    gig(joel, ucu, "errands-moving", "Help moving hostel rooms on Saturday morning", 40_000, "in_person", "Moving from one hostel to another (about 1km) in Mukono. Mattress, desk, two boxes and a small fridge. Need one strong person for about 2 hours. I'll cover boda transport for the items.", 1, 3, "Mukono, near UCU gate")
    gig(amina, mak, "photo-video", "Photographer for faculty dinner – 3 hours", 150_000, "in_person", "Our faculty dinner is at the Main Hall. We need someone with their own camera to take event photos for about 3 hours and deliver edited photos within one week.", 2, 10, "Main Hall, Makerere")
    gig(brian, kyu, "tutoring", "Calculus I tutor – 4 evening sessions", 100_000, "either", "I need help understanding limits, differentiation and integration before my exams. 4 sessions of about 90 minutes each. Online or in person at the library is fine.", 1, 14)
    gig(grace, mubs, "tech-repairs", "Laptop won't boot past the logo – need diagnosis", 50_000, "in_person", "Dell Inspiron stuck on the logo screen after an update. Need someone who can diagnose and fix it without losing my files. Price can change after diagnosis.", 3, None, "Nakawa")
    gig(amina, mak, "printing-documents", "Format and bind 5 copies of project report (80 pages)", 60_000, "in_person", "Report is done; I need help with formatting (table of contents, page numbers, margins per department guidelines), then printing and spiral binding 5 copies.", 0, 4, "Wandegeya")
    gig(joel, ucu, "photo-video", "Edit a 2-minute promo video for our club", 70_000, "remote", "We have raw clips from our club activities. Need a fun 2 minute edit with music and captions for Instagram and TikTok.", 4, 7)
    gig(brian, kyu, "events", "2 ushers for career fair registration desk", 60_000, "in_person", "Need two friendly people to handle registration for our department career fair, 8am–1pm. Lunch provided. Budget is per person.", 2, 6, "Kyambogo main hall")

    def biz(name, kind, desc, address, phone, slug):
        return Business.objects.create(owner=owner, name=name, slug=slug, kind=kind, description=desc, address=address, phone=phone,
                                       verification="verified", verified_at=now, is_sample=True)

    food = biz("Mama Rose Kitchen (sample)", "Restaurant / Café", "Home-style Ugandan food near campus: rolex, chips, matooke, beans and daily specials.", "Wandegeya, opposite the market", "+256700000101", "mama-rose-kitchen-sample")
    prnt = biz("Kikoni Print Hub (sample)", "Print shop", "Printing, photocopying, binding and lamination for students. Same-day service.", "Kikoni, near Makerere western gate", "+256700000102", "kikoni-print-hub-sample")
    tech = biz("TechFix Wandegeya (sample)", "Electronics", "Phone and laptop repairs, accessories and screen replacements.", "Wandegeya, Plot 12", "+256700000103", "techfix-wandegeya-sample")
    cuts = biz("Campus Cuts Barbershop (sample)", "Salon / Barber", "Clean cuts, shaves and styling for students.", "Kikoni Road", "+256700000104", "campus-cuts-sample")

    def deal(b, title, label, desc, orig, price, ends, campus, cap):
        Deal.objects.create(business=b, title=title, discount_label=label, description=desc, original_price_ugx=orig, deal_price_ugx=price,
                            ends_at=_ahead(ends), campus=campus, max_claims=cap, status="active", is_sample=True,
                            terms="One claim per student. Show your code at the counter.")

    deal(food, "Rolex + juice combo for students", "25% off", "Two-egg rolex with a fresh passion juice, any time after 4pm.", 8_000, 6_000, 14, mak, 200)
    deal(prnt, "50 pages black & white printing", "UGX 4,000", "Print up to 50 A4 pages B/W for a flat price. Bring your file on flash or send on WhatsApp.", 5_000, 4_000, 30, None, None)
    deal(tech, "Free screen protector with any phone repair", "Free gift", "Get a tempered glass screen protector free with any repair above UGX 30,000.", None, None, 21, None, 100)
    deal(cuts, "Student haircut", "UGX 8,000", "Any standard cut for students, Monday to Thursday.", 12_000, 8_000, 10, mak, 150)

    Report.objects.create(reporter=student, target_type="listing", target_id=sold.pk, reason="misleading",
                          details="Sample report so the moderation queue isn't empty in development.")
    from core.sample_art import attach_sample_images

    attach_sample_images()
    return True
