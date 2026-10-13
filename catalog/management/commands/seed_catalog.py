from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Attribute, AttributeValue, Category, Product
from rates.models import Probe

# адрес, название, кыргызча, English, название одного изделия
CATEGORIES = [
    ("rings", "Кольца", "Шакектер", "Rings", "Кольцо"),
    ("earrings", "Серьги", "Сөйкөлөр", "Earrings", "Серьги"),
    ("chains", "Цепи", "Чынжырлар", "Chains", "Цепь"),
    ("bracelets", "Браслеты", "Билериктер", "Bracelets", "Браслет"),
    ("pendants", "Подвески", "Кулондор", "Pendants", "Подвеска"),
]

ATTRIBUTES = {
    "Цвет металла": ["Жёлтое золото", "Белое золото", "Красное золото"],
    "Материал": ["Золото", "Серебро"],
    "Вставка": ["Без вставки", "Фианит", "Бриллиант"],
    "Для кого": ["Для женщин", "Для мужчин", "Детям"],
    "Тип замка": ["Английский", "Карабин", "Шпрингельный"],
}

# размеры и вес первого изделия в категории: (размер, вес в граммах)
VARIANTS = {
    "rings": [("16", "1.80"), ("17", "2.00"), ("18", "2.20")],
    "earrings": [("", "2.60")],
    "chains": [("45 см", "3.50"), ("50 см", "3.90"), ("55 см", "4.30")],
    "bracelets": [("17 см", "4.00"), ("19 см", "4.50")],
    "pendants": [("", "1.40")],
}

PRODUCTS_PER_CATEGORY = 5


class Command(BaseCommand):
    help = "Наполняет каталог тестовыми товарами. Повторный запуск не создаёт дубли"

    @transaction.atomic
    def handle(self, *args, **options):
        probes = list(Probe.objects.filter(is_active=True))
        if not probes:
            raise CommandError("Нет ни одной пробы. Сначала добавьте пробы в админке: «Курс и калькулятор» → «Пробы».")

        values = self.create_attributes()
        created = 0
        for slug, name, name_ky, name_en, item_name in CATEGORIES:
            category, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name, "name_ky": name_ky, "name_en": name_en})
            for number in range(1, PRODUCTS_PER_CATEGORY + 1):
                created += self.create_product(category, item_name, number, probes, values)

        self.stdout.write(self.style.SUCCESS(f"Готово: создано товаров - {created}, всего в каталоге - {Product.objects.count()}"))

    def create_attributes(self):
        """Создаёт характеристики и возвращает их значения: {"Камень": [значения], ...}."""
        result = {}
        for name, value_names in ATTRIBUTES.items():
            attribute, _ = Attribute.objects.get_or_create(name=name)
            result[name] = [AttributeValue.objects.get_or_create(attribute=attribute, value=value)[0] for value in value_names]
        return result

    def create_product(self, category, item_name, number, probes: Probe, values):
        """Создаёт один товар с вариантами. Возвращает 1, если товар новый, и 0, если он уже был."""
        product, is_new = Product.objects.get_or_create (
            slug = f"seed-{category.slug}-{number}",
            defaults={
                "category": category,
                "probe": probes[number % len(probes)],
                "name": f"{item_name} «Образец {number}»",
                "description": "Тестовый товар для проверки каталога.",
                "surcharge": Decimal(number * 100),
            },
        )

        if not is_new:
            return 0

        for index, (size, weight) in enumerate(VARIANTS[category.slug]):
            product.variants.create (
                size=size,
                weight=weight,
                in_stock=not (number == 3 and index == 0), # у третьего товара первого размера нет в наличии
                custom_price = Decimal("9990") if number == 5 and index == 0 else None,
            )
        product.attribute_values.set([group[number % len(group)] for group in values.values()])
        return 1



