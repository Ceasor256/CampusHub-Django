from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from core.models import Campus, Review
from core.utils import assert_active, audit, conflict, invalid

User = get_user_model()
VERIFY_SALT = "campushub.verify-email"
VERIFY_MAX_AGE = 3 * 24 * 3600


def register_user(*, full_name, email, phone, password):
    if User.objects.filter(email__iexact=email).exists():
        raise conflict("An account with this email already exists. Try logging in instead.")
    user = User.objects.create_user(email=email, password=password, full_name=full_name, phone=phone or "")
    audit(user, "user.register", "user", user.pk)
    return user


# ------------------------------------------------------------------ email verification
def send_verification_email(user):
    token = signing.dumps({"uid": str(user.pk), "email": user.email}, salt=VERIFY_SALT)
    link = settings.APP_URL + reverse("accounts:verify_email", args=[token])
    send_mail(
        "Confirm your CampusHub email",
        f"Hi {user.first_name_display},\n\nConfirm your email to earn a trust badge on CampusHub:\n{link}\n\n"
        "This link expires in 3 days. If you didn't sign up, ignore this email.",
        None,
        [user.email],
    )


def verify_email(token):
    try:
        data = signing.loads(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
    except signing.BadSignature:
        raise invalid("This link is invalid or has expired. Request a new one from your account page.")
    # Email in the token must still match, so old links die if the email changes.
    user = User.objects.filter(pk=data["uid"], email=data["email"]).first()
    if not user:
        raise invalid("This link is invalid or has expired.")
    if not user.email_verified_at:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


# ------------------------------------------------------------------ password reset
def send_password_reset(email):
    """Always behaves the same whether or not the account exists (no account discovery)."""
    user = User.objects.filter(email__iexact=email).exclude(status="deleted").first()
    if not user:
        return
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = settings.APP_URL + reverse("accounts:reset_password", args=[uid, token])
    send_mail(
        "Reset your CampusHub password",
        f"Someone asked to reset your CampusHub password. If it was you, open:\n{link}\n\n"
        "This link expires in 1 hour and works once. If it wasn't you, ignore this email.",
        None,
        [user.email],
    )


def user_from_reset_link(uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError, signing.BadSignature, Exception):
        return None
    # Tokens are tied to the password hash, so they stop working once used.
    return user if default_token_generator.check_token(user, token) and user.status != "deleted" else None


def reset_password(user, password):
    user.set_password(password)  # changing the hash invalidates every existing session
    user.save(update_fields=["password"])
    audit(user, "user.password_reset", "user", user.pk)


# ------------------------------------------------------------------ profile
def set_campus(user, campus_id):
    campus = Campus.objects.filter(pk=campus_id, is_active=True, institution__is_active=True).first()
    if not campus:
        raise invalid("Choose an available campus.")
    user.campus = campus


def complete_onboarding(user, *, campus_id, phone):
    assert_active(user)
    set_campus(user, campus_id)
    if phone:
        user.phone = phone
    user.onboarded_at = timezone.now()
    user.save(update_fields=["campus", "phone", "onboarded_at"])


def update_profile(user, *, full_name, phone, bio, campus_id):
    assert_active(user)
    user.full_name, user.phone, user.bio = full_name, phone or "", bio or ""
    set_campus(user, campus_id)
    user.save(update_fields=["full_name", "phone", "bio", "campus"])


def rating_summary(user):
    r = Review.objects.filter(reviewee=user).aggregate(avg=Avg("rating"), n=Count("id"))
    return {"rating": round(r["avg"], 1) if r["avg"] else None, "review_count": r["n"]}


@transaction.atomic
def delete_account(user, password):
    """
    Removes personal data and keeps an anonymised tombstone so transaction and
    moderation history stay intact.
    """
    if not user.check_password(password):
        raise invalid("Password is incorrect.")
    from gigs.models import Gig
    from marketplace.models import Listing

    Listing.objects.filter(seller=user, status__in=["active", "paused"]).update(status="removed")
    Gig.objects.filter(poster=user, status="open").update(status="cancelled", cancel_reason="Poster deleted account")
    user.full_name = "Deleted user"
    user.email = f"deleted+{user.pk}@invalid.campushub"
    user.phone = ""
    user.bio = ""
    user.status = User.Status.DELETED
    user.is_active = False  # blocks login entirely
    user.set_password(get_random_string(40))
    user.save()
    audit(user, "user.delete_account", "user", user.pk)
