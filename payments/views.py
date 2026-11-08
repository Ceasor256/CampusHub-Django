from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .providers import get_provider, handle_webhook


@csrf_exempt  # authenticated by the provider's HMAC signature instead of a CSRF token
@require_POST
def webhook(request, provider):
    try:
        p = get_provider(provider)
    except LookupError:
        return HttpResponse("unknown provider", status=404)
    status, body = handle_webhook(p, request.body, request.headers)
    return HttpResponse(body, status=status, content_type="text/plain")
