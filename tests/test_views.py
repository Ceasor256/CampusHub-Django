"""
End-to-end HTTP tests through Django's test client: real URLs, templates,
forms, CSRF-free test client, sessions and permissions.
"""

import io
import re
import shutil
import tempfile

from django.core import mail
from django.test import TestCase, override_settings
from PIL import Image

from accounts.models import User
from core.models import Report
from core.seed import seed_reference, seed_samples
from deals.models import Deal, DealClaim
from gigs.models import Gig
from marketplace.models import Listing
from messaging.models import Message

MEDIA = tempfile.mkdtemp()


def png_bytes():
    buf = io.BytesIO()
    img = Image.new("RGB", (300, 200), "#6633d1")
    img.save(buf, "PNG")
    buf.seek(0)
    buf.name = "photo.png"
    return buf


@override_settings(MEDIA_ROOT=MEDIA, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", ALLOWED_HOSTS=["testserver"])
class ViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference()
        seed_samples()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def login(self, email, password):
        r = self.client.post("/login/", {"email": email, "password": password})
        self.assertEqual(r.status_code, 302, "login failed")

    def test_public_pages_render(self):
        listing = Listing.objects.filter(status="active").first()
        gig = Gig.objects.first()
        deal = Deal.objects.first()
        for url in ["/", "/marketplace/", "/marketplace/?q=casio&sort=price_asc&campus=all", "/gigs/", "/gigs/?mode=remote", "/deals/",
                    "/services/", "/sell/", "/safety/", "/terms/", "/privacy/", "/business/", "/login/", "/register/", "/forgot-password/",
                    f"/marketplace/{listing.pk}/", f"/gigs/{gig.pk}/", f"/deals/{deal.pk}/", f"/b/{deal.business.slug}/", f"/u/{listing.seller.pk}/"]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
        self.assertEqual(self.client.get("/marketplace/00000000-0000-0000-0000-000000000000/").status_code, 404)
        self.assertEqual(self.client.get("/does-not-exist/").status_code, 404)

    def test_3d_story_on_home_and_tour(self):
        from django.contrib.staticfiles import finders

        home = self.client.get("/")
        tour = self.client.get("/tour/")
        self.assertEqual(tour.status_code, 200)
        for r in (home, tour):
            html = r.content.decode()
            self.assertIn("data-story", html)
            self.assertIn("js/story-scene.js", html)  # loaded on demand, not with a <script> tag
            self.assertIsNone(re.search(r"<script[^>]*story-scene", html))
            self.assertEqual(html.count('class="story-chapter"'), 5)
        # The tour's first chapter is the page heading; the homepage keeps its own h1 in the hero.
        self.assertContains(tour, '<h1 class="story-title">')
        self.assertEqual(home.content.decode().count("<h1"), 1)
        # The bundled scene and loader are real files.
        self.assertTrue(finders.find("js/story.js"))
        self.assertTrue(finders.find("js/story-scene.js"))

    def test_member_pages_require_login(self):
        for url in ["/me/", "/settings/", "/messages/", "/notifications/", "/marketplace/new/", "/gigs/new/", "/staff/"]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/login/", r["Location"])

    def test_register_onboard_list_message_report_flow(self):
        r = self.client.post("/register/", {"full_name": "Esther N", "email": "Esther@Test.ug", "phone": "0772 123 456", "password": "Kampala-Rocks-2026", "agree": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)  # verification email
        u = User.objects.get(email="esther@test.ug")
        self.assertEqual(u.phone, "+256772123456")
        # Unonboarded users are sent to onboarding first.
        self.assertIn("/onboarding/", self.client.get("/marketplace/new/")["Location"])
        from core.models import Campus, Category

        campus = Campus.objects.get(slug="mak-main-campus")
        self.assertEqual(self.client.post("/onboarding/", {"campus": campus.pk}).status_code, 302)

        # Verify email via the emailed link (GET shows a button, POST confirms).
        link = re.search(r"http://\S+", mail.outbox[0].body).group(0)
        path = link.split("8010", 1)[1]
        self.assertEqual(self.client.get(path).status_code, 200)
        self.client.post(path)
        self.assertIsNotNone(User.objects.get(pk=u.pk).email_verified_at)

        # Validation errors re-render the form.
        r = self.client.post("/marketplace/new/", {"title": "x", "price_ugx": "abc"})
        self.assertContains(r, "Please fix the highlighted fields.")
        cat = Category.objects.get(module="marketplace", slug="books-stationery")
        r = self.client.post("/marketplace/new/", {"title": "Casio fx-991EX ClassWiz", "category": cat.pk, "condition": "like_new",
                                                   "description": "Used for one semester. Comes with cover.", "price_ugx": "85,000",
                                                   "is_negotiable": "on", "campus": campus.pk, "images": [png_bytes()]})
        self.assertEqual(r.status_code, 302)
        listing = Listing.objects.get(title="Casio fx-991EX ClassWiz")
        self.assertEqual(listing.price_ugx, 85_000)
        img = listing.images.get()
        self.assertTrue(img.image.name.endswith(".webp"))  # re-encoded, EXIF stripped
        detail = self.client.get(f"/marketplace/{listing.pk}/")
        self.assertContains(detail, "UGX 85,000")
        self.assertContains(detail, "Mark as sold")

        # A fake "image" is rejected.
        bad = io.BytesIO(b"<svg onload=alert(1)></svg>")
        bad.name = "evil.png"
        r = self.client.post("/marketplace/new/", {"title": "Bad upload test", "category": cat.pk, "condition": "good",
                                                   "description": "This should never be saved.", "price_ugx": "1000", "campus": campus.pk, "images": [bad]})
        self.assertContains(r, "isn&#x27;t a valid image")

        # Message a sample seller, then report their listing.
        other = Listing.objects.filter(is_sample=True, status="active").exclude(seller=u).first()
        r = self.client.post("/messages/start/", {"recipient": other.seller.pk, "listing": other.pk, "body": "Is this still available?"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Message.objects.filter(sender=u, body="Is this still available?").exists())
        self.assertEqual(self.client.get(r["Location"]).status_code, 200)
        self.client.post("/report/", {"target_type": "listing", "target_id": other.pk, "reason": "misleading", "details": "test"}, HTTP_REFERER=f"/marketplace/{other.pk}/")
        self.assertTrue(Report.objects.filter(reporter=u, target_id=other.pk).exists())

        # Students can't reach staff pages or actions.
        self.assertEqual(self.client.get("/staff/")["Location"], "/")
        self.client.post("/staff/act/suspend_user/", {"id": other.seller.pk, "reason": "nope nope"})
        self.assertEqual(User.objects.get(pk=other.seller.pk).status, "active")

        # Other users can't edit someone else's listing.
        self.assertEqual(self.client.get(f"/marketplace/{other.pk}/edit/").status_code, 404)
        self.client.post(f"/marketplace/{other.pk}/delete/")
        self.assertTrue(Listing.objects.filter(pk=other.pk).exists())

        # Every member page renders.
        for url in ["/me/", "/me/?tab=gigs", "/me/?tab=saved", "/me/?tab=deals", "/me/?tab=purchases", "/settings/", "/messages/", "/notifications/", "/gigs/new/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_claim_deal_and_gig_application(self):
        self.login("student@campushub.test", "StudentDev2026!")
        deal = Deal.objects.filter(campus__isnull=True).first()
        self.client.post(f"/deals/{deal.pk}/claim/")
        self.client.post(f"/deals/{deal.pk}/claim/")  # second claim returns the same code
        self.assertEqual(DealClaim.objects.filter(deal=deal).count(), 1)
        self.assertContains(self.client.get(f"/deals/{deal.pk}/"), DealClaim.objects.get(deal=deal).code)

        gig = Gig.objects.filter(status="open").first()
        r = self.client.post(f"/gigs/{gig.pk}/apply/", {"message": "I have done this before, can start today.", "proposed_ugx": "45000"})
        self.assertEqual(r.status_code, 302)
        self.assertContains(self.client.get(f"/gigs/{gig.pk}/"), "Your application")

    def test_staff_pages_and_moderation(self):
        self.login("admin@campushub.test", "AdminDev2026!")
        for url in ["/staff/", "/staff/?days=7&samples=1", "/staff/reports/", "/staff/reports/?status=dismissed", "/staff/users/", "/staff/users/?q=sample",
                    "/staff/businesses/", "/staff/deals/", "/staff/transactions/", "/staff/campuses/", "/staff/categories/", "/staff/settings/", "/staff/audit/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        report = Report.objects.filter(status="open").first()
        self.client.post("/staff/act/resolve_report/", {"id": report.pk, "outcome": "dismiss", "note": "test"})
        self.assertEqual(Report.objects.get(pk=report.pk).status, "dismissed")
        self.client.post("/staff/act/commissions/", {"marketplace": "4.5", "gigs": "8", "enabled": "on"})
        from core.settings_store import get_commissions

        self.assertEqual(get_commissions().rates["marketplace"], 450)
        self.assertContains(self.client.get("/staff/audit/"), "settings.commissions.update")

    def test_moderator_cannot_use_admin_only_actions(self):
        self.login("moderator@campushub.test", "ModDev2026!")
        self.assertEqual(self.client.get("/staff/settings/").status_code, 302)
        self.client.post("/staff/act/commissions/", {"marketplace": "50", "gigs": "50", "enabled": "on"})
        from core.settings_store import get_commissions

        self.assertFalse(get_commissions().enabled)
        student = User.objects.get(email="student@campushub.test")
        self.client.post("/staff/act/set_role/", {"id": student.pk, "role": "admin", "grant": "1"})
        self.assertNotIn("admin", User.objects.get(pk=student.pk).roles)
