from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from rates.models import Probe

from .models import Category, Product
from .filters import active_filters, apply_filters, attribute_groups, counted, price_bounds, size_options, quick_filters
from .filters import SORT_NAMES, SORT_SHORT_NAMES, SORTS

PAGE_SIZE = 12

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

    base = Product.objects.visible()  # товары страницы до фильтров: по ним считаются числа в панели
    if category:
        base = base.filter(category=category)
    products = apply_filters(base.select_related("probe").prefetch_related("images"), request.GET)

    page = Paginator(products, PAGE_SIZE).get_page(request.GET.get("page"))
    context = {"category": category, "page": page, "total": page.paginator.count}

    # Запрос от HTMX: без шапки и формы. Кнопка «Назад» в браузере — исключение: тогда HTMX просит страницу целиком
    is_htmx = request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request")
    if is_htmx and request.GET.get("page"):  # «Показать ещё»: только следующие карточки, фильтры не менялись
        return render(request, "catalog/_cards.html", context)

    probes = counted(Probe.objects.filter(is_active=True), base)
    groups = attribute_groups(base)
    sort = request.GET.get("sort") if request.GET.get("sort") in SORTS else "popular"
    active = active_filters(request.GET, categories, probes, groups)
    context |= {
        "active": active,
        # «Сбросить»: категория тоже считается выбранным фильтром, сортировка — нет и сохраняется
        "reset_count": len(active) + (1 if category else 0),
        "reset_url": reverse("catalog") + (f"?sort={sort}" if sort != "popular" else ""),
        "quick": quick_filters(request.GET, groups),
    }

    # Смена фильтра: карточки и попутно число товаров и чипы ряда
    if is_htmx:
        return render(request, "catalog/_results.html", context)

    context |= {
        "categories": categories,
        "category_counts": counted(categories, base),
        "probes": probes,
        "groups": groups,
        "sizes": size_options(base),
        "bounds": price_bounds(base),
        "selected_probes": request.GET.getlist("probe"),
        "selected_values": request.GET.getlist("value"),
        "sort": sort,
        "sort_name": SORT_NAMES[sort],
        "sort_short_name": SORT_SHORT_NAMES[sort],
        "sorts": SORT_NAMES.items(),
    }
    return render(request, "catalog/list.html", context)

