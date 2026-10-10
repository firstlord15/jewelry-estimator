from django.db.models import Max
from django.http import JsonResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from django.conf import settings
from django.shortcuts import render
from django.utils import translation
from django.utils.translation import gettext as _

from .models import Probe, QuickWeight


@require_GET
@cache_control(public=True, max_age=60)
def rates_api(request):
    """Текущий курс: только пробы, отмеченные «показывать на сайте».

    Названия металлов и валюты отдаются на языке из ?lang=: адрес API без языкового префикса,
    а с языком в адресе ответ можно кешировать отдельно для каждого языка.
    """
    lang = request.GET.get("lang")
    if lang not in dict(settings.LANGUAGES):
        lang = translation.get_language()

    with translation.override(lang):
        probes = Probe.objects.filter(is_active=True)
        updated_at = probes.aggregate(last=Max("updated_at"))["last"]

        data = {
            "currency": "KGS",
            "currency_label": _("сом"),
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