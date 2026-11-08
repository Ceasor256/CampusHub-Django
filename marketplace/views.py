from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render

from core.forms import MessageForm
from core.images import process_images
from core.models import Category
from core.utils import AppError, parse_ugx, throttle
from core.web import active_campuses, browse_campus, form_error, member_required, or_404, post_action

from . import services
from .forms import ListingForm, MarkSoldForm
from .models import Favourite, Listing


def browse(request):
    campus = browse_campus(request)
    g = request.GET
    qs = services.search(q=g.get("q", ""), campus=campus, category=g.get("category", ""), condition=g.get("condition", ""),
                         min_price=parse_ugx(g.get("min")), max_price=parse_ugx(g.get("max")), sort=g.get("sort", "newest"))
    page = Paginator(qs, services.PAGE_SIZE).get_page(g.get("page"))
    cats = Category.objects.filter(module="marketplace", is_active=True)
    return render(request, "marketplace/browse.html", {
        "page": page, "campus": campus, "campuses": active_campuses(), "categories": cats,
        "active_category": cats.filter(slug=g.get("category", "")).first(), "conditions": Listing.Condition.choices,
    })


def _listing_form_data(form):
    d = form.cleaned_data
    return {k: d[k] for k in ("title", "description", "price_ugx", "is_negotiable", "category", "condition", "campus", "meetup_note")}


@member_required
def create(request):
    form = ListingForm(request.POST or None, initial={"campus": request.user.campus})
    if request.method == "POST":
        try:
            throttle(request, f"listing:{request.user.pk}", 20, 3600)
            if form.is_valid():
                images = process_images(request.FILES.getlist("images"))
                listing = services.create_listing(request.user, _listing_form_data(form), images)
                messages.success(request, "Your listing is live! Buyers can now message you.")
                return redirect("marketplace:detail", listing.pk)
        except AppError as e:
            form_error(form, e)
    return render(request, "marketplace/form.html", {"form": form})


@member_required
def edit(request, listing_id):
    listing, is_owner = or_404(services.get_for_viewer, listing_id, request.user)
    if not is_owner or listing.status == Listing.Status.SOLD:
        raise Http404
    initial = {f: getattr(listing, f) for f in ("title", "description", "price_ugx", "is_negotiable", "category", "condition", "campus", "meetup_note")}
    form = ListingForm(request.POST or None, initial=initial)
    if request.method == "POST":
        try:
            if form.is_valid():
                keep = request.POST.getlist("keep")
                kept_ids = [i.pk for i in listing.images.all() if str(i.pk) in keep]
                images = process_images(request.FILES.getlist("images"), already=len(kept_ids))
                services.update_listing(request.user, listing.pk, _listing_form_data(form), keep_ids=kept_ids, new_images=images)
                messages.success(request, "Changes saved.")
                return redirect("marketplace:detail", listing.pk)
        except AppError as e:
            form_error(form, e)
    return render(request, "marketplace/form.html", {"form": form, "listing": listing})


def detail(request, listing_id):
    user = request.user
    listing, is_owner = or_404(services.get_for_viewer, listing_id, user)
    if not is_owner:
        services.increment_views(listing)
    ctx = {
        "l": listing,
        "is_owner": is_owner,
        "images": list(listing.images.all()),
        "seller_stats": services.seller_stats(listing.seller),
        "is_favourite": user.is_authenticated and Favourite.objects.filter(user=user, listing=listing).exists(),
        "message_form": MessageForm(initial={"body": f"Hi, is the {listing.title[:40]} still available?"}),
    }
    from accounts.services import rating_summary

    ctx["seller_rating"] = rating_summary(listing.seller)
    if is_owner:
        ctx["sold_form"] = MarkSoldForm(contacts=services.contacts(user, listing), initial={"final_price": listing.price_ugx})
    return render(request, "marketplace/detail.html", ctx)


@post_action
def pause(request, listing_id):
    paused = request.POST.get("paused") == "1"
    services.set_paused(request.user, listing_id, paused)
    messages.success(request, "Listing paused. It's hidden from search." if paused else "Listing is live again.")
    return redirect("marketplace:detail", listing_id)


@post_action
def delete(request, listing_id):
    services.delete_listing(request.user, listing_id)
    messages.success(request, "Listing deleted.")
    return redirect("/me/?tab=listings")


@post_action
def mark_sold(request, listing_id):
    listing = Listing.objects.filter(pk=listing_id).first()
    if not listing:
        raise Http404
    form = MarkSoldForm(request.POST, contacts=services.contacts(request.user, listing))
    if not form.is_valid():
        messages.error(request, "; ".join(e for errs in form.errors.values() for e in errs))
        return redirect("marketplace:detail", listing_id)
    services.mark_sold(request.user, listing_id, buyer_id=form.cleaned_data["buyer"] or None, final_price=form.cleaned_data["final_price"])
    messages.success(request, "Marked as sold. Congratulations on the sale!")
    return redirect("marketplace:detail", listing_id)


@post_action
def favourite(request, listing_id):
    saved = services.toggle_favourite(request.user, listing_id)
    messages.success(request, "Saved to your list." if saved else "Removed from saved.")
    return redirect("marketplace:detail", listing_id)
