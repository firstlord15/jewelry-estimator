from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from rates.models import Probe

from .models import Category, Product
from .filters import active_filters, apply_filters, attribute_groups, counted, price_bounds, size_options



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

    if request.headers.get("HX-Request") and not request.headers.get("HX-History-Restore-Request"):
        return render(request, "catalog/_cards.html", context)

    probes = counted(Probe.objects.filter(is_active=True), base)
    groups = attribute_groups(base)
    context |= {
        "categories": categories,
        "category_counts": counted(categories, base),
        "probes": probes,
        "groups": groups,
        "sizes": size_options(base),
        "bounds": price_bounds(base),
        "active": active_filters(request.GET, categories, probes, groups),
        "selected_probes": request.GET.getlist("probe"),
        "selected_values": request.GET.getlist("value"),
    }
    return render(request, "catalog/list.html", context)

