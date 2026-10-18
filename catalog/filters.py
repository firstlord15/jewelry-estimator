import re
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from django.db.models import Count, F, Max, Min, Prefetch, Q
from django.template.defaultfilters import floatformat
from django.utils.translation import gettext as _, gettext_lazy

from rates.models import Probe

from .models import Attribute, AttributeValue, Category, ProductVariant


class Sort(NamedTuple):
    order: list  # для order_by
    name: str  # полное название: в открытом меню
    short: str  # короткое: на кнопке


# Ключ — значение ?sort= в адресе. Новая сортировка — одна строка здесь, остальное подхватится само
SORTS = {
    "popular": Sort(["-views", "-created_at"], gettext_lazy("Сначала популярные"), gettext_lazy("Популярные")),
    "new": Sort(["-created_at"], gettext_lazy("Сначала новые"), gettext_lazy("Новинки")),
    "cheap": Sort([F("price_from").asc(nulls_last=True)], gettext_lazy("Сначала дешевле"), gettext_lazy("Дешевле")),
    "expensive": Sort([F("price_from").desc(nulls_last=True)], gettext_lazy("Сначала дороже"), gettext_lazy("Дороже")),
}
DEFAULT_SORT = "popular"


def sort_key(params):
    """Сортировка из адреса. Неизвестная или пустая — по умолчанию."""
    key = params.get("sort")
    return key if key in SORTS else DEFAULT_SORT


def to_decimal(text):
    """Цена из адреса: «1 500,50» → 1500.50. Не число, «nan», «Infinity» и отрицательное — None, фильтра нет."""
    try:
        value = Decimal(text.replace(",", ".").replace(" ", ""))
    except (InvalidOperation, AttributeError):
        return None
    return value if value.is_finite() and value >= 0 else None


def text_values(params, key):
    """Значения параметра без нулевого символа: PostgreSQL не принимает его в тексте, а боты шлют такое нарочно."""
    return [v for v in params.getlist(key) if "\x00" not in v]


# Параметры адреса, которые отбирают товары. sort и page не в счёт
FILTER_KEYS = ("category", "probe", "value", "size", "price_min", "price_max", "in_stock")


def has_filters(params):
    """Выбран ли хоть один фильтр. Пустые price_min= и price_max= от формы не считаются."""
    return any(params.get(key) for key in FILTER_KEYS)


def value_attributes(params):
    """К какой характеристике относится каждое выбранное значение: {"16": 8}. Один запрос, без значений — ни одного."""
    ids = [v for v in params.getlist("value") if v.isdigit()]
    return {str(pk): attribute for pk, attribute in AttributeValue.objects.filter(pk__in=ids).values_list("pk", "attribute_id")}


def apply_filters(products, params, attributes=None):
    """Товары по фильтрам из адреса. attributes — готовый ответ value_attributes, чтобы не спрашивать базу повторно."""
    slugs = text_values(params, "category")
    if slugs:
        products = products.filter(category__slug__in=slugs)

    probe_ids = [p for p in params.getlist("probe") if p.isdigit()]
    if probe_ids:
        products = products.filter(probe_id__in=probe_ids)

    # характеристики: внутри одной «или» (фианит или бриллиант), между разными «и» (камень и цвет)
    if attributes is None:
        attributes = value_attributes(params)
    by_attribute = {}
    for value in params.getlist("value"):
        if value in attributes:
            by_attribute.setdefault(attributes[value], []).append(value)
    for ids in by_attribute.values():
        products = products.filter(attribute_values__in=ids)

    # до with_price(): тогда цена «от» считается по выбранным размерам, а не по всем
    sizes = text_values(params, "size")
    if sizes:
        products = products.filter(variants__size__in=sizes, variants__in_stock=True)

    products = products.with_price() # цена нужна для фильтров ниже

    if params.get("in_stock"):
        products = products.filter(price_from__isnull=False)
    if (price_min := to_decimal(params.get("price_min"))) is not None:
        products = products.filter(price_from__gte=price_min)
    if (price_max := to_decimal(params.get("price_max"))) is not None:
        products = products.filter(price_from__lte=price_max)

    return products.order_by(*SORTS[sort_key(params)].order)


def counted(queryset, base):
    """Добавляет каждой записи count: сколько товаров из base к ней привязано. Пустые убирает."""
    return queryset.annotate(count=Count("products", filter=Q(products__in=base), distinct=True)).filter(count__gt=0)


def attribute_groups(base):
    """Характеристики для фильтра со значениями и числом товаров."""
    attributes = Attribute.objects.filter(is_filter=True).prefetch_related(
        Prefetch("values", queryset=counted(AttributeValue.objects.all(), base))
    )
    return [attribute for attribute in attributes if attribute.values.all()]


def facet_counts(base, params, categories, probes, groups, attributes):
    """Пересчитывает count у галочек панели под выбранные фильтры, как на маркетплейсах.

    Галочки своей группы при этом не учитываются: внутри группы они складываются через «или»,
    и число показывает, сколько товаров найдётся, если отметить ещё и это значение.
    Отмечены «Кольца»: у «Цепочек» остаётся 6, а у пробы 585 — только кольца этой пробы.
    Один запрос на группу, а не на каждое значение. attributes — ответ value_attributes.
    """

    def found(key, drop=None):
        """Товары по всем выбранным фильтрам, кроме галочек группы key (или только значений drop)."""
        query = params.copy()
        query.setlist(key, [] if drop is None else [v for v in query.getlist(key) if v not in drop])
        return apply_filters(base, query, attributes).values("pk")

    def recount(items, model, key, drop=None):
        numbers = dict(
            model.objects.filter(pk__in=[item.pk for item in items])
            .annotate(n=Count("products", filter=Q(products__in=found(key, drop)), distinct=True))
            .values_list("pk", "n")
        )
        for item in items:
            item.count = numbers.get(item.pk, 0)

    recount(categories, Category, "category")
    recount(probes, Probe, "probe")
    for group in groups:  # у характеристик своя группа — значения одной характеристики, а не весь параметр value
        values = list(group.values.all())
        recount(values, AttributeValue, "value", drop={str(value.pk) for value in values})


def mark_checked(params, categories, probes, groups):
    """Ставит каждой галочке панели checked: отмечена ли она в адресе. Как count — свойством самой записи."""
    chosen = {key: set(params.getlist(key)) for key in ("category", "probe", "value")}
    for item in categories:
        item.checked = item.slug in chosen["category"]
    for item in probes:
        item.checked = str(item.pk) in chosen["probe"]
    for group in groups:
        for item in group.values.all():
            item.checked = str(item.pk) in chosen["value"]


def size_order(size):
    """Ключ сортировки размеров по числу в начале: «9» раньше «10», «16.5» между 16 и 17. Без числа — в конец."""
    number = re.match(r"\d+(?:[.,]\d+)?", size)
    return (float(number.group().replace(",", ".")) if number else float("inf"), size)


def size_options(base, params):
    """Размеры, которые есть в наличии у товаров страницы, и отмечен ли каждый: [{"value": "17", "checked": True}]."""
    variants = ProductVariant.objects.filter(product__in=base, in_stock=True).exclude(size="")
    # order_by() сбрасывает порядок модели (товар, вес): иначе distinct учитывает и его, и размеры повторяются
    sizes = sorted(variants.values_list("size", flat=True).order_by().distinct(), key=size_order)
    chosen = set(params.getlist("size"))
    return [{"value": size, "checked": size in chosen} for size in sizes]


def price_bounds(base):
    """Края ползунка цены, округлённые до сотен: нижний вниз, верхний вверх."""
    bounds = base.with_price().aggregate(low=Min("price_from"), high=Max("price_from"))
    if bounds["low"] is None:  # в наличии ничего нет
        return None
    return {"low": int(bounds["low"] // 100 * 100), "high": int(-(-bounds["high"] // 100) * 100)}


def with_value(params, key, value):
    """Адрес текущей страницы с ещё одним значением фильтра."""
    query = params.copy()
    query.appendlist(key, str(value))
    query.pop("page", None)
    return "?" + query.urlencode()


def quick_filters(params, groups):
    """Быстрые фильтры («Бриллиант»), которые ещё не выбраны: название и адрес с этим фильтром."""
    chosen = params.getlist("value")
    return [
        {"label": value.value_local, "url": with_value(params, "value", value.pk)}
        for group in groups
        for value in group.values.all()
        if value.is_quick and str(value.pk) not in chosen
    ]


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

    for size in text_values(params, "size"):
        add(_("Размер %(size)s") % {"size": size}, "size", size)

    # Цена одним чипом: «от 10 000 до 175 000 сом». Крестик убирает обе границы.
    # Через to_decimal, как в apply_filters: «абв» в адресе цену не фильтрует, и чипа для неё нет
    price_min, price_max = to_decimal(params.get("price_min")), to_decimal(params.get("price_max"))
    if price_min is not None or price_max is not None:
        parts = []
        if price_min is not None:
            parts.append(_("от %(price)s") % {"price": floatformat(price_min, "-2g")})
        if price_max is not None:
            parts.append(_("до %(price)s") % {"price": floatformat(price_max, "-2g")})
        query = params.copy()
        query.pop("price_max", None)
        chips.append({"label": " ".join(parts) + " " + _("сом"), "url": without(query, "price_min")})

    if params.get("in_stock"):
        add(_("В наличии"), "in_stock")
    return chips
