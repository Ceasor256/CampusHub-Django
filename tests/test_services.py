"""
Business-rule tests against a real database (Django test DB), exercising the
service layer exactly as views do. Mirrors the Next.js integration suite.
"""

import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts import services as accounts
from accounts.models import StaffRole, User
from core.models import Campus, Category, Report
from core.seed import seed_reference
from core.settings_store import CommissionSettings, save_commissions
from core.utils import AppError
from deals import services as deals
from deals.models import Deal
from gigs import services as gigs
from gigs.models import Gig
from marketplace import services as market
from marketplace.models import Listing
from messaging import services as msg
from payments.models import Payment, Transaction
from payments.providers import TestPaymentProvider, handle_webhook
from staff import services as staff


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference()
        cls.campus = Campus.objects.first()
        cls.mcat = Category.objects.filter(module="marketplace").first()
        cls.gcat = Category.objects.filter(module="gigs").first()

    def user(self, name, role=None):
        u = accounts.register_user(full_name=name, email=f"{name.lower().replace(' ', '.')}@test.local", phone="", password="Password123!")
        accounts.complete_onboarding(u, campus_id=self.campus.pk, phone="")
        if role:
            StaffRole.objects.create(user=u, role=role)
        return User.objects.get(pk=u.pk)  # fresh instance (roles cache)

    def listing_data(self, **kw):
        return {"title": "Casio calculator", "description": "Works well, used one semester.", "price_ugx": 45_000, "is_negotiable": False,
                "category": self.mcat, "condition": "good", "campus": self.campus, "meetup_note": "", **kw}

    def gig_data(self, **kw):
        return {"title": "Design a poster for our club", "description": "Need an A3 poster with our logo and event details.", "budget_ugx": 50_000,
                "category": self.gcat, "campus": self.campus, "mode": "remote", "location_note": "", "deadline": None, **kw}

    def assertAppError(self, code, fn, *a, **kw):
        with self.assertRaises(AppError) as ctx:
            fn(*a, **kw)
        self.assertEqual(ctx.exception.code, code, ctx.exception.message)


class AccountTests(Base):
    def test_duplicate_email_is_case_insensitive(self):
        accounts.register_user(full_name="Dup", email="dup@test.local", phone="", password="Password123!")
        self.assertAppError("conflict", accounts.register_user, full_name="Dup", email="DUP@test.local", phone="", password="x")

    def test_email_verification_token(self):
        u = self.user("Verify Me")
        from django.core import signing
        token = signing.dumps({"uid": str(u.pk), "email": u.email}, salt=accounts.VERIFY_SALT)
        accounts.verify_email(token)
        u.refresh_from_db()
        self.assertIsNotNone(u.email_verified_at)
        self.assertAppError("invalid", accounts.verify_email, token + "x")

    def test_delete_account_anonymises_and_hides_content(self):
        u = self.user("Leaving Lucy")
        l = market.create_listing(u, self.listing_data(), [])
        self.assertAppError("invalid", accounts.delete_account, u, "wrong")
        accounts.delete_account(u, "Password123!")
        u.refresh_from_db()
        l.refresh_from_db()
        self.assertEqual((u.status, u.full_name, u.is_active, l.status), ("deleted", "Deleted user", False, "removed"))


class MarketplaceTests(Base):
    def test_crud_search_and_ownership(self):
        seller, other = self.user("Seller One"), self.user("Other Person")
        l = market.create_listing(seller, self.listing_data(), [])
        self.assertIn(l, market.search(q="casio", campus=self.campus))
        self.assertAppError("forbidden", market.update_listing, other, l.pk, self.listing_data(), keep_ids=[], new_images=[])
        market.update_listing(seller, l.pk, self.listing_data(price_ugx=40_000), keep_ids=[], new_images=[])
        l.refresh_from_db()
        self.assertEqual(l.price_ugx, 40_000)
        market.set_paused(seller, l.pk, True)
        self.assertNotIn(l, market.search(q="casio"))
        self.assertAppError("not_found", market.get_for_viewer, l.pk, other)
        market.delete_listing(seller, l.pk)
        self.assertFalse(Listing.objects.filter(pk=l.pk).exists())

    def test_mark_sold_once_with_fee_only_when_enabled(self):
        admin, seller, buyer = self.user("Fee Admin", "admin"), self.user("Seller Two"), self.user("Buyer Two")
        l = market.create_listing(seller, self.listing_data(), [])
        msg.start_conversation(buyer, recipient=seller, listing=l, body="Is it available?")
        save_commissions(admin, CommissionSettings(enabled=True, rates={"marketplace": 500, "gigs": 1000}))
        tx = market.mark_sold(seller, l.pk, buyer_id=buyer.pk, final_price=40_001)
        self.assertEqual((tx.fee_ugx, tx.fee_status, tx.payment_status), (2_000, "accrued", "offline_unverified"))
        self.assertAppError("conflict", market.mark_sold, seller, l.pk, buyer_id=None, final_price=1)

    def test_buyer_must_have_messaged_the_seller(self):
        seller, stranger = self.user("Seller Three"), self.user("Stranger Three")
        l = market.create_listing(seller, self.listing_data(), [])
        self.assertAppError("invalid", market.mark_sold, seller, l.pk, buyer_id=stranger.pk, final_price=10)

    def test_suspended_users_cannot_post(self):
        u = self.user("Suspended Sam")
        u.status = "suspended"
        u.save()
        self.assertAppError("forbidden", market.create_listing, u, self.listing_data(), [])


class GigTests(Base):
    def test_full_lifecycle(self):
        poster, worker, loser = self.user("Gig Poster"), self.user("Gig Worker"), self.user("Gig Loser")
        g = gigs.create_gig(poster, self.gig_data())
        self.assertAppError("invalid", gigs.apply, poster, g.pk, message="own gig!!", proposed_ugx=1000)
        gigs.apply(worker, g.pk, message="I can do this today", proposed_ugx=45_000)
        gigs.apply(loser, g.pk, message="Pick me please", proposed_ugx=40_000)
        self.assertAppError("conflict", gigs.apply, worker, g.pk, message="again again", proposed_ugx=1)
        app = g.applications.get(applicant=worker)
        self.assertAppError("forbidden", gigs.accept, worker, app.pk)
        gigs.accept(poster, app.pk)
        self.assertEqual(g.applications.get(applicant=loser).status, "rejected")
        self.assertEqual(gigs.confirm_completion(worker, g.pk), "waiting")
        self.assertEqual(gigs.confirm_completion(poster, g.pk), "completed")
        tx = Transaction.objects.get(reference_id=g.pk)
        self.assertEqual((tx.amount_ugx, tx.seller_id), (45_000, worker.pk))
        gigs.review(poster, g.pk, rating=5, comment="Great work")
        self.assertAppError("conflict", gigs.review, poster, g.pk, rating=4, comment="")
        self.assertAppError("forbidden", gigs.review, loser, g.pk, rating=1, comment="")
        self.assertEqual(accounts.rating_summary(worker)["rating"], 5)

    def test_dispute_goes_to_moderators(self):
        poster, worker, mod = self.user("D Poster"), self.user("D Worker"), self.user("D Mod", "moderator")
        g = gigs.create_gig(poster, self.gig_data())
        gigs.apply(worker, g.pk, message="I'll do it now", proposed_ugx=50_000)
        gigs.accept(poster, g.applications.get().pk)
        gigs.dispute(worker, g.pk, "Poster is not responding after delivery")
        self.assertTrue(any(r["r"].target_id == g.pk for r in staff.list_reports(mod)))
        self.assertAppError("forbidden", staff.resolve_dispute, poster, g.pk, "completed", "x")
        staff.resolve_dispute(mod, g.pk, "completed", "Delivery confirmed")
        self.assertEqual(Gig.objects.get(pk=g.pk).status, "completed")


class DealTests(Base):
    def test_review_claim_cap_and_single_redemption(self):
        owner, s1, s2, mod = self.user("Biz Owner"), self.user("Student A"), self.user("Student B"), self.user("Deal Mod", "moderator")
        b = deals.create_business(owner, {"name": "Test Café", "kind": "Restaurant / Café", "description": "Coffee and snacks for students.",
                                          "phone": "+256772000000", "email": "", "address": "Wandegeya"})
        d = deals.create_deal(owner, b.pk, {"title": "Coffee discount", "description": "20% off any coffee", "terms": "", "discount_label": "20% off",
                                            "original_price_ugx": 5000, "deal_price_ugx": 4000, "campus": None, "redemption": "unique_code",
                                            "shared_code": "", "max_claims": 1, "ends_at": timezone.now() + timedelta(days=1)})
        self.assertEqual(d.status, "pending_review")
        self.assertAppError("conflict", deals.claim, s1, d.pk)
        staff.moderate_deal(mod, d.pk, "active")
        c1 = deals.claim(s1, d.pk)
        self.assertEqual(deals.claim(s1, d.pk).code, c1.code)  # idempotent per user
        self.assertAppError("conflict", deals.claim, s2, d.pk)  # cap reached
        self.assertEqual(Deal.objects.get(pk=d.pk).claim_count, 1)
        self.assertAppError("forbidden", deals.redeem, s2, b.pk, c1.code)
        deals.redeem(owner, b.pk, c1.code.lower())
        self.assertAppError("conflict", deals.redeem, owner, b.pk, c1.code)


class MessagingAndModerationTests(Base):
    def test_privacy_unread_reports_and_permissions(self):
        a, b, c, mod = self.user("Msg A"), self.user("Msg B"), self.user("Msg C"), self.user("Msg Mod", "moderator")
        conv = msg.start_conversation(a, recipient=b, body="Hello")
        self.assertEqual(msg.start_conversation(a, recipient=b, body="Hello again").pk, conv.pk)
        self.assertEqual(msg.unread_message_count(b), 2)
        self.assertEqual(msg.unread_message_count(a), 0)
        self.assertAppError("not_found", msg.open_conversation, c, conv.pk)
        msg.open_conversation(b, conv.pk)
        self.assertEqual(msg.unread_message_count(b), 0)
        msg.send(b, conv.pk, "Reply")
        self.assertEqual(msg.unread_message_count(a), 1)

        l = market.create_listing(a, self.listing_data(), [])
        staff.create_report(c, target_type="listing", target_id=l.pk, reason="scam_or_fraud", details="")
        self.assertAppError("conflict", staff.create_report, c, target_type="listing", target_id=l.pk, reason="spam", details="")
        report = Report.objects.get(target_id=l.pk)
        self.assertAppError("forbidden", staff.resolve_report, c, report.pk, outcome="remove", note="")
        staff.resolve_report(mod, report.pk, outcome="remove_and_suspend", note="Scam confirmed")
        self.assertEqual(Listing.objects.get(pk=l.pk).status, "removed")
        self.assertEqual(User.objects.get(pk=a.pk).status, "suspended")
        self.assertAppError("forbidden", staff.set_role, mod, c.pk, "admin", True)
        self.assertAppError("forbidden", staff.platform_metrics, c)
        self.assertGreaterEqual(staff.platform_metrics(mod)["users"]["total"], 4)


class PaymentWebhookTests(Base):
    def test_signature_idempotency_and_amount_check(self):
        payer = self.user("Payer")
        p = TestPaymentProvider("secret")
        ref = p.initiate()
        Payment.objects.create(payer=payer, provider="test", provider_ref=ref, method="mtn_momo", amount_ugx=10_000, is_test=True)
        body = json.dumps({"eventId": "evt_1", "providerRef": ref, "status": "succeeded", "amountUgx": 10_000}).encode()
        self.assertEqual(handle_webhook(p, body, {"X-CampusHub-Signature": "nope"})[0], 401)
        h = {"X-CampusHub-Signature": p.sign(body)}
        self.assertEqual(handle_webhook(p, body, h), (200, "ok"))
        self.assertEqual(handle_webhook(p, body, h), (200, "duplicate ignored"))
        self.assertEqual(Payment.objects.get(provider_ref=ref).status, "succeeded")
        ref2 = p.initiate()
        Payment.objects.create(payer=payer, provider="test", provider_ref=ref2, method="mtn_momo", amount_ugx=10_000, is_test=True)
        body2 = json.dumps({"eventId": "evt_2", "providerRef": ref2, "status": "succeeded", "amountUgx": 1}).encode()
        self.assertEqual(handle_webhook(p, body2, {"X-CampusHub-Signature": p.sign(body2)})[0], 422)
