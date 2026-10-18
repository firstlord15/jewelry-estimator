from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from rates.models import Probe

from .models import Category, Product
from .filters import active_filters, apply_filters, attribute_groups, counted, facet_counts, has_filters, mark_checked, price_bounds, quick_filters, size_options, value_attributes
from .filters import DEFAULT_SORT, SORTS, sort_key

PAGE_SIZE = 12

def product_detail(request, slug):
    products = (
        Product.objects.visible()
        .select_related("category", "probe")
        .prefetch_related("images", "variants", "attribute_values__attribute")
    )
    product = get_object_or_404(products, slug=slug)
    Product.objects.filter(pk=product.pk).update(views=F("views") + 1)
    variants = list(product.variants.all())
    selected = next((v for v in variants if v.in_stock), variants[0] if variants else None)
    return render(request, "catalog/detail.html", {"product": product, "variants": variants, "selected": selected})


def product_list(request, category_slug=None):
    categories = Category.objects.filter(is_active=True)
    category = get_object_or_404(categories, slug=category_slug) if category_slug else None

    base = Product.objects.visible()  # товары страницы до фильтров: по ним считаются числа в панели
    if category:
        base = base.filter(category=category)
    attributes = value_attributes(request.GET)  # один раз на запрос: нужен и для товаров, и для чисел в панели
    products = apply_filters(base.select_related("probe").prefetch_related("images"), request.GET, attributes)

    page = Paginator(products, PAGE_SIZE).get_page(request.GET.get("page"))
    context = {"category": category, "page": page, "total": page.paginator.count}

    # Запрос от HTMX: без шапки и формы. Кнопка «Назад» в браузере — исключение: тогда HTMX просит страницу целиком
    is_htmx = request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request")
    if is_htmx and request.GET.get("page"):  # «Показать ещё»: только следующие карточки, фильтры не менялись
        return render(request, "catalog/cards/grid.html", context)

    # Списки галочек панели — по всей странице, а числа у них — под выбранные фильтры.
    # Ничего не выбрано — числа уже верные (их посчитал counted), пересчёт дал бы те же самые
    category_counts = list(counted(categories, base))
    probes = list(counted(Probe.objects.filter(is_active=True), base))
    groups = attribute_groups(base)
    active = active_filters(request.GET, categories, probes, groups)
    if has_filters(request.GET):
        facet_counts(base, request.GET, category_counts, probes, groups, attributes)
    sort = sort_key(request.GET)
    context |= {
        "active": active,
        # «Сбросить»: категория тоже считается выбранным фильтром, сортировка — нет и сохраняется
        "reset_count": len(active) + (1 if category else 0),
        "reset_url": reverse("catalog") + (f"?sort={sort}" if sort != DEFAULT_SORT else ""),
        "quick": quick_filters(request.GET, groups),
        "category_counts": category_counts,
        "probes": probes,
        "groups": groups,
    }

    # Смена фильтра: карточки и попутно число товаров, чипы ряда и числа у галочек панели
    if is_htmx:
        return render(request, "catalog/list/results.html", context)

    mark_checked(request.GET, category_counts, probes, groups)  # галочки нужны только всей странице: HTMX панель не меняет
    context |= {
        "categories": categories,
        "sizes": size_options(base, request.GET),
        "bounds": price_bounds(base),
        "sort": sort,
        "sort_changed": sort != DEFAULT_SORT,  # кнопка сортировки залита, если порядок не по умолчанию
        "current_sort": SORTS[sort],
        "sorts": SORTS,
    }
    return render(request, "catalog/list.html", context)

