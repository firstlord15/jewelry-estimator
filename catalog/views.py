from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, render

from rates.models import Probe

from .models import Attribute, AttributeValue, Category, Product


PAGE_SIZE = 12

SORTS = {
    "new": ["-created_at"],
    "cheap": [F("price_from").asc(nulls_last=True)],
    "expensive": [F("price_from").desc(nulls_last=True)],
}


def to_decimal(text):
    try:
        return Decimal(text.replace(",", ".").replace(" ", ""))
    except (InvalidOperation, AttributeError):
        return None


def apply_filters(products, params):
    if params.get("metal") in ("gold", "silver"):
        products = products.filter(probe__metal=params["metal"])

    probe_ids = [p for p in params.getlist("probe") if p.isdigit()]
    if probe_ids:
        products = products.filter(probe_id__in=probe_ids)

    # характеристики: внутри одной «или» (фианит или бриллиант), между разными «и» (камень и цвет)
    value_ids = [v for v in params.getlist("value") if v.isdigit()]
    by_attribute = {}
    for value in AttributeValue.objects.filter(pk__in=value_ids):
        by_attribute.setdefault(value.attribute_id, []).append(value.pk)
    for ids in by_attribute.values():
        products = products.filter(attribute_values__in=ids)

    products = products.with_price() # цена нужна для фильтров ниже

    if params.get("in_stock"):
        products = products.filter(price_from__isnull=False)
    if (price_min := to_decimal(params.get("price_min"))) is not None:
        products = products.filter(price_from__gte=price_min)
    if (price_max := to_decimal(params.get("price_max"))) is not None:
        products = products.filter(price_from__lte=price_max)

    return products.order_by(*SORTS.get(params.get("sort"), SORTS["new"]))


def product_detail(request, slug):
    products = (
        Product.objects.visible()
        .select_related("category", "probe")
        .prefetch_related("images", "variants", "attribute_values__attribute")
    )
    product = get_object_or_404(products, slug=slug)
    variants = list(product.variants.all())
    selected = next((v for v in variants if v.in_stock), variants[0] if variants else None)
    return render(request, "catalog/detail.html", {"product": product, "variants": variants, "selected": selected})


def product_list(request, category_slug=None):
    categories = Category.objects.filter(is_active=True)
    category = get_object_or_404(categories, slug=category_slug) if category_slug else None

    products = Product.objects.visible().select_related("probe").prefetch_related("images")
    if category:
        products = products.filter(category=category)
    products = apply_filters(products, request.GET)

    page = Paginator(products, PAGE_SIZE).get_page(request.GET.get("page"))
    context = {"category": category, "page": page}

    # Запрос от HTMX (смена фильтра, «Показать ещё»): отдаём только карточки, без шапки и формы.
    # Кнопка «Назад» в браузере — исключение: тогда HTMX просит страницу целиком
    if request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request"):
        return render(request, "catalog/_cards.html", context)

    context |= {
        "categories": categories,
        "probes": Probe.objects.filter(is_active=True),
        "attributes": Attribute.objects.prefetch_related("values"),
        # что отмечено в форме: чтобы галочки не сбрасывались после отправки
        "selected_probes": request.GET.getlist("probe"),
        "selected_values": request.GET.getlist("value"),
    }
    return render(request, "catalog/list.html", context)
