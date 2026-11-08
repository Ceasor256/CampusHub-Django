from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts import views as acc
from core import views as core
from deals import views as deals
from gigs import views as gigs
from marketplace import views as market
from messaging import views as msg
from payments import views as pay
from staff import views as staff

core_urls = ([
    path("", core.home, name="home"),
    path("campus/", core.set_campus, name="set_campus"),
    path("services/", core.services, name="services"),
    path("sell/", core.sell, name="sell"),
    path("safety/", core.page("core/safety.html"), name="safety"),
    path("terms/", core.page("core/terms.html"), name="terms"),
    path("privacy/", core.page("core/privacy.html"), name="privacy"),
    path("report/", core.report, name="report"),
    path("notifications/", core.notifications, name="notifications"),
    path("dev/outbox/", core.dev_outbox, name="outbox"),
], "core")

account_urls = ([
    path("register/", acc.register, name="register"),
    path("login/", acc.login_view, name="login"),
    path("logout/", acc.logout_view, name="logout"),
    path("onboarding/", acc.onboarding, name="onboarding"),
    path("forgot-password/", acc.forgot_password, name="forgot_password"),
    path("reset/<str:uidb64>/<str:token>/", acc.reset_password, name="reset_password"),
    path("verify-email/resend/", acc.resend_verification, name="resend_verification"),
    path("verify-email/<str:token>/", acc.verify_email, name="verify_email"),
    path("me/", acc.me, name="me"),
    path("settings/", acc.settings_view, name="settings"),
    path("settings/delete/", acc.delete_account, name="delete_account"),
    path("u/<uuid:user_id>/", acc.profile, name="profile"),
], "accounts")

market_urls = ([
    path("", market.browse, name="browse"),
    path("new/", market.create, name="create"),
    path("<uuid:listing_id>/", market.detail, name="detail"),
    path("<uuid:listing_id>/edit/", market.edit, name="edit"),
    path("<uuid:listing_id>/pause/", market.pause, name="pause"),
    path("<uuid:listing_id>/delete/", market.delete, name="delete"),
    path("<uuid:listing_id>/sold/", market.mark_sold, name="sold"),
    path("<uuid:listing_id>/favourite/", market.favourite, name="favourite"),
], "marketplace")

gig_urls = ([
    path("", gigs.browse, name="browse"),
    path("new/", gigs.create, name="create"),
    path("<uuid:gig_id>/", gigs.detail, name="detail"),
    path("<uuid:gig_id>/apply/", gigs.apply, name="apply"),
    path("<uuid:gig_id>/withdraw/", gigs.withdraw, name="withdraw"),
    path("<uuid:gig_id>/accept/<uuid:application_id>/", gigs.accept, name="accept"),
    path("<uuid:gig_id>/confirm/", gigs.confirm, name="confirm"),
    path("<uuid:gig_id>/cancel/", gigs.cancel, name="cancel"),
    path("<uuid:gig_id>/dispute/", gigs.dispute, name="dispute"),
    path("<uuid:gig_id>/review/", gigs.review, name="review"),
], "gigs")

deal_urls = ([
    path("deals/", deals.browse, name="browse"),
    path("deals/<uuid:deal_id>/", deals.detail, name="detail"),
    path("deals/<uuid:deal_id>/claim/", deals.claim, name="claim"),
    path("b/<slug:slug>/", deals.business_public, name="business_public"),
    path("business/", deals.business_home, name="business_home"),
    path("business/<uuid:business_id>/", deals.dashboard, name="dashboard"),
    path("business/<uuid:business_id>/deals/new/", deals.new_deal, name="new_deal"),
    path("business/<uuid:business_id>/verify/", deals.request_verification, name="request_verification"),
    path("business/<uuid:business_id>/redeem/", deals.redeem, name="redeem"),
    path("business/<uuid:business_id>/deals/<uuid:deal_id>/pause/", deals.pause_deal, name="pause_deal"),
], "deals")

msg_urls = ([
    path("", msg.inbox, name="inbox"),
    path("start/", msg.start, name="start"),
    path("<uuid:conv_id>/", msg.conversation, name="conversation"),
], "messaging")

staff_urls = ([
    path("", staff.overview, name="overview"),
    path("reports/", staff.reports, name="reports"),
    path("users/", staff.users, name="users"),
    path("businesses/", staff.businesses, name="businesses"),
    path("deals/", staff.deals, name="deals"),
    path("transactions/", staff.transactions, name="transactions"),
    path("campuses/", staff.campuses, name="campuses"),
    path("categories/", staff.categories, name="categories"),
    path("settings/", staff.platform_settings, name="settings"),
    path("audit/", staff.audit_log, name="audit"),
    path("act/<slug:op>/", staff.act, name="act"),
], "staff")

urlpatterns = [
    path("", include(core_urls)),
    path("", include(account_urls)),
    path("", include(deal_urls)),
    path("marketplace/", include(market_urls)),
    path("gigs/", include(gig_urls)),
    path("messages/", include(msg_urls)),
    path("staff/", include(staff_urls)),
    path("payments/webhook/<slug:provider>/", pay.webhook, name="payment_webhook"),
    path("django-admin/", admin.site.urls),  # superusers only (technical back office)
]

handler404 = "core.views.error_404"
handler500 = "core.views.error_500"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
