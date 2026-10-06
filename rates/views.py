from django.db.models import Max
from django.http import JsonResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from .models import Probe, QuickWeight
from django.shortcuts import render
from django.conf import settings


@require_GET
@cache_control(public=True, max_age=60)
def rates_api(request):
    """Текущий курс: только пробы, отмеченные «показывать на сайте»."""
    probes = Probe.objects.filter(is_active=True)
    updated_at = probes.aggregate(last=Max("updated_at"))["last"]

    data = {
        "currency": "KGS",
        "currency_label": "сом",
        "updated_at": updated_at.isoformat() if updated_at else None,
        "quick_weights": [
            f"{w.grams.normalize():f}" for w in QuickWeight.objects.filter(is_active=True)
        ],
        "rates": [
            {
                "id": p.id,
                "metal": p.metal,
                "metal_label": p.get_metal_display(),
                "fineness": p.fineness,
                "price_per_gram": str(p.price_per_gram),
            }
            for p in probes
        ],
    }
    return JsonResponse(data, json_dumps_params={"ensure_ascii": False})

def index(request):
    return render(request, "rates/index.html", {
        "show_qty": settings.CALC_SHOW_QUANTITY,
    })