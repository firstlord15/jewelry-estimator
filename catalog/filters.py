from decimal import Decimal, InvalidOperation

from django.utils.translation import gettext as _
from django.db.models import Count, F, Max, Min, Prefetch, Q

from .models import Attribute, AttributeValue, ProductVariant

SORTS = {
    "popular": ["-views", "-created_at"],
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
    slugs = params.getlist("category")
    if slugs:
        products = products.filter(category__slug__in=slugs)

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
    
    # до with_price(): тогда цена «от» считается по выбранным размерам, а не по всем
    sizes = params.getlist("size")
    if sizes:
        products = products.filter(variants__size__in=sizes, variants__in_stock=True)

    products = products.with_price() # цена нужна для фильтров ниже

    if params.get("in_stock"):
        products = products.filter(price_from__isnull=False)
    if (price_min := to_decimal(params.get("price_min"))) is not None:
        products = products.filter(price_from__gte=price_min)
    if (price_max := to_decimal(params.get("price_max"))) is not None:
        products = products.filter(price_from__lte=price_max)

    return products.order_by(*SORTS.get(params.get("sort"), SORTS["popular"]))


def counted(queryset, base):
    """Добавляет каждой записи count: сколько товаров из base к ней привязано. Пустые убирает."""
    return queryset.annotate(count=Count("products", filter=Q(products__in=base), distinct=True)).filter(count__gt=0)


def attribute_groups(base):
    """Характеристики для фильтра со значениями и числом товаров."""
    attributes = Attribute.objects.filter(is_filter=True).prefetch_related(
        Prefetch("values", queryset=counted(AttributeValue.objects.all(), base))
    )
    return [attribute for attribute in attributes if attribute.values.all()]


def size_options(base):
    """Размеры, которые есть в наличии у товаров страницы."""
    variants = ProductVariant.objects.filter(product__in=base, in_stock=True).exclude(size="")
    return list(variants.values_list("size", flat=True).distinct().order_by("size"))


def price_bounds(base):
    """Края ползунка цены, округлённые до сотен: нижний вниз, верхний вверх."""
    bounds = base.with_price().aggregate(low=Min("price_from"), high=Max("price_from"))
    if bounds["low"] is None:  # в наличии ничего нет
        return None
    return {"low": int(bounds["low"] // 100 * 100), "high": int(-(-bounds["high"] // 100) * 100)}

def without(params, key, value=None):
    """Адрес текущей страницы без одного значения фильтра. Без value убирает параметр целиком."""
    query = params.copy()
    query.setlist(key, [] if value is None else [v for v in query.getlist(key) if v != str(value)])
    query.pop("page", None)
    return "?" + query.urlencode()


def active_filters(params, categories, probes, groups):
    """Выбранные фильтры для кнопок над товарами: название и адрес без этого фильтра."""
    chips = []

    def add(label, key, value=None):
        chips.append({"label": label, "url": without(params, key, value)})

    chosen = params.getlist("category")
    for category in categories:
        if category.slug in chosen:
            add(category.name_local, "category", category.slug)

    chosen = params.getlist("probe")
    for probe in probes:
        if str(probe.pk) in chosen:
            add(str(probe), "probe", probe.pk)

    chosen = params.getlist("value")
    for group in groups:
        for value in group.values.all():
            if str(value.pk) in chosen:
                add(value.value_local, "value", value.pk)

    for size in params.getlist("size"):
        add(_("Размер %(size)s") % {"size": size}, "size", size)
    if params.get("price_min"):
        add(_("от %(price)s") % {"price": params["price_min"]}, "price_min")
    if params.get("price_max"):
        add(_("до %(price)s") % {"price": params["price_max"]}, "price_max")
    if params.get("in_stock"):
        add(_("В наличии"), "in_stock")
    return chips
