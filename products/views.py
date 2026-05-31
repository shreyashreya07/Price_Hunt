from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
import json

from .scraper import search_products

# Import model safely — if table doesn't exist yet it won't crash the whole view
try:
    from .models import SearchHistory
    HISTORY_ENABLED = True
except Exception:
    HISTORY_ENABLED = False


# ─────────────────────────────────────────────────────────
#  HELPER: normalize a price value to plain int
# ─────────────────────────────────────────────────────────
def clean_price(price):
    """
    Handles int, float, or string like '₹1,23,456' → int.
    Returns 0 on any failure so sorting never crashes.
    """
    try:
        if isinstance(price, (int, float)):
            return int(price)
        return int(str(price).replace('₹', '').replace(',', '').strip())
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────
#  HELPER: normalize + filter + sort + cap to 10
# ─────────────────────────────────────────────────────────
def prepare_products(raw, min_price=None, max_price=None):
    for p in raw:
        p['price'] = clean_price(p.get('price', 0))

    if min_price is not None:
        raw = [p for p in raw if p['price'] >= min_price]
    if max_price is not None:
        raw = [p for p in raw if p['price'] <= max_price]

    raw.sort(key=lambda x: x['price'])
    return raw[:10]


# ─────────────────────────────────────────────────────────
#  HELPER: save search query to history
#  Wrapped in its own try/except so a DB issue NEVER
#  prevents products from being shown to the user.
# ─────────────────────────────────────────────────────────
def _save_history(query):
    if not HISTORY_ENABLED:
        return
    try:
        # Use only the 'query' field — safe even if model has no searched_at column
        SearchHistory.objects.create(query=query)
    except Exception as e:
        # Log but never bubble up — history is non-critical
        print(f"[history] Could not save: {e}")


# ─────────────────────────────────────────────────────────
#  VIEW: Home / Search Page
# ─────────────────────────────────────────────────────────
@require_GET
def index(request):
    query     = request.GET.get('query', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()

    products  = []
    error     = None

    min_val = int(min_price) if min_price.isdigit() else None
    max_val = int(max_price) if max_price.isdigit() else None

    if query:
        # ── Save history SEPARATELY so it never blocks product fetch ──
        _save_history(query)

        # ── Fetch & prepare products ──
        try:
            raw      = search_products(query, min_price=min_val, max_price=max_val)
            products = prepare_products(raw, min_val, max_val)

            if not products:
                error = "No products found. Try a different search term or widen your price range."

        except Exception as e:
            error = "Something went wrong while fetching products. Please try again."
            print(f"[index] Scraper error: {e}")

    return render(request, 'products/index.html', {
        'products':  products,
        'query':     query,
        'error':     error,
        'min_price': min_price,
        'max_price': max_price,
    })


# ─────────────────────────────────────────────────────────
#  VIEW: JSON API
# ─────────────────────────────────────────────────────────
@require_GET
def api_products(request):
    query     = request.GET.get('query', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()

    if not query:
        return JsonResponse({'error': 'query parameter is required'}, status=400)

    min_val = int(min_price) if min_price.isdigit() else None
    max_val = int(max_price) if max_price.isdigit() else None

    try:
        raw      = search_products(query, min_price=min_val, max_price=max_val)
        products = prepare_products(raw, min_val, max_val)
        return JsonResponse({'query': query, 'count': len(products), 'results': products})
    except Exception as e:
        print(f"[api_products] Error: {e}")
        return JsonResponse({'error': 'Failed to fetch products.'}, status=500)


# ─────────────────────────────────────────────────────────
#  VIEW: Set Price Alert  POST /api/alert/
#  Body JSON: { "email": "...", "product": "...", "price": 49999 }
# ─────────────────────────────────────────────────────────
@csrf_exempt
@require_POST
def set_price_alert(request):
    try:
        body    = json.loads(request.body)
        email   = body.get('email', '').strip()
        product = body.get('product', '').strip()
        price   = body.get('price')

        if not email or not product or price is None:
            return JsonResponse(
                {'error': 'email, product, and price are all required'},
                status=400
            )

        ok = _send_alert_email(email, product, int(price))
        if ok:
            return JsonResponse({'message': f'Alert set! We will notify {email} about price changes.'})
        return JsonResponse({'error': 'Email delivery failed. Check server EMAIL settings.'}, status=500)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)
    except Exception as e:
        print(f"[set_price_alert] Error: {e}")
        return JsonResponse({'error': 'Unexpected error.'}, status=500)


# ─────────────────────────────────────────────────────────
#  VIEW: Search History  GET /api/history/
# ─────────────────────────────────────────────────────────
@require_GET
def search_history(request):
    if not HISTORY_ENABLED:
        return JsonResponse({'history': []})
    try:
        history = list(
            SearchHistory.objects
            .order_by('-id')
            .values('query')[:20]
        )
        return JsonResponse({'history': history})
    except Exception as e:
        print(f"[search_history] Error: {e}")
        return JsonResponse({'error': 'Could not fetch history.'}, status=500)


# ─────────────────────────────────────────────────────────
#  INTERNAL: send price alert email
# ─────────────────────────────────────────────────────────
def _send_alert_email(email, product, price):
    try:
        send_mail(
            subject=f"🔥 Price Alert — {product}",
            message=(
                f"Great news!\n\n"
                f"{product} is now available at ₹{price:,}.\n\n"
                f"Visit PriceHunt to grab the deal:\n"
                f"https://yourdomain.com\n\n"
                f"— The PriceHunt Team"
            ),
            from_email="alerts@pricehunt.com",
            recipient_list=[email],
            fail_silently=False,
        )
        print(f"[email] Sent to {email} → '{product}' at ₹{price:,}")
        return True
    except Exception as e:
        print(f"[email] Failed: {e}")
        return False


# ─────────────────────────────────────────────────────────
#  VIEW: Test email — remove before deploying to production
# ─────────────────────────────────────────────────────────
def test_email(request):
    ok = _send_alert_email("test@example.com", "iPhone 15 Pro 256GB", 89999)
    if ok:
        return HttpResponse("✅ Test email sent successfully.")
    return HttpResponse("❌ Email failed. Check EMAIL_* settings in settings.py.")