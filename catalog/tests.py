from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import connection
from django.db.models import ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import translation

from core.models import ChangeLog
from rates.models import Probe

from .models import Attribute, AttributeValue, Category, Product, ProductImage, ProductVariant


class CatalogData:
    """Общие данные для тестов каталога: проба 585 по 5000 сом за грамм и категория «Кольца»."""

    def setUp(self):
        self.probe = Probe.objects.create(metal="gold", fineness=585, price_per_gram=Decimal("5000"))
        self.category = Category.objects.create(name="Кольца", slug="rings")

    def new_product(self, slug="ring", **fields):
        return Product.objects.create(category=self.category, probe=self.probe, name=f"Кольцо {slug}", slug=slug, **fields)


class SkuTests(CatalogData, TestCase):
    """Артикул: число, создаётся само, не повторяется и не меняется."""

    def test_sku_is_created_automatically(self):
        product = self.new_product()
        self.assertEqual(product.sku, Product.SKU_START + product.pk)
        self.assertGreater(product.sku, 100_000)
        self.assertEqual(Product.objects.get(pk=product.pk).sku, product.sku)  # записан в базу

    def test_sku_is_unique(self):
        self.assertNotEqual(self.new_product("a").sku, self.new_product("b").sku)

    def test_sku_does_not_change_on_resave(self):
        product = self.new_product()
        sku = product.sku
        product.name = "Кольцо с фианитом"
        product.save()
        self.assertEqual(Product.objects.get(pk=product.pk).sku, sku)


class PriceTests(CatalogData, TestCase):
    """Цена варианта: расчётная следует за курсом, своя цена её заменяет."""

    def test_calculated_price(self):
        variant = self.new_product(surcharge=Decimal("500")).variants.create(size="17", weight=Decimal("2.35"))
        self.assertEqual(variant.price, Decimal("12250.00"))  # 2.35 × 5000 + 500

    def test_calculated_price_is_rounded_to_tyiyns_half_up(self):
        self.probe.price_per_gram = Decimal("4800.50")
        self.probe.save()
        variant = self.new_product().variants.create(weight=Decimal("2.35"))
        self.assertEqual(variant.price, Decimal("11281.18"))  # 11281.175 → вверх, как в калькуляторе

    def test_price_follows_the_rate(self):
        variant = self.new_product().variants.create(weight=Decimal("2"))
        self.assertEqual(variant.price, Decimal("10000.00"))

        self.probe.price_per_gram = Decimal("6000")
        self.probe.save()
        self.assertEqual(ProductVariant.objects.get(pk=variant.pk).price, Decimal("12000.00"))

    def test_custom_price_replaces_calculated_and_ignores_the_rate(self):
        variant = self.new_product().variants.create(weight=Decimal("2"), custom_price=Decimal("9999.90"))
        self.assertEqual(variant.price, Decimal("9999.90"))  # как введена, без округления

        self.probe.price_per_gram = Decimal("6000")
        self.probe.save()
        variant = ProductVariant.objects.get(pk=variant.pk)
        self.assertEqual(variant.price, Decimal("9999.90"))
        self.assertEqual(variant.calculated_price, Decimal("12000.00"))  # расчётная видна рядом

    def test_zero_or_empty_custom_price_means_calculated(self):
        variant = self.new_product().variants.create(weight=Decimal("2"), custom_price=Decimal("12000"))
        for empty in (Decimal("0"), None):
            with self.subTest(empty):
                variant.custom_price = empty
                variant.save()
                variant = ProductVariant.objects.get(pk=variant.pk)
                self.assertIsNone(variant.custom_price)
                self.assertEqual(variant.price, Decimal("10000.00"))

    def test_min_price_is_the_lowest_in_stock(self):
        product = self.new_product()
        product.variants.create(size="16", weight=Decimal("1"), in_stock=False)  # дешевле, но нет в наличии
        product.variants.create(size="17", weight=Decimal("2"))
        product.variants.create(size="18", weight=Decimal("3"))
        self.assertEqual(product.min_price, Decimal("10000.00"))

    def test_min_price_counts_custom_prices(self):
        product = self.new_product()
        product.variants.create(size="17", weight=Decimal("2"))
        product.variants.create(size="18", weight=Decimal("3"), custom_price=Decimal("7000"))
        self.assertEqual(product.min_price, Decimal("7000"))

    def test_min_price_is_none_when_nothing_in_stock(self):
        product = self.new_product()
        self.assertIsNone(product.min_price)  # вариантов нет
        product.variants.create(weight=Decimal("2"), in_stock=False)
        self.assertIsNone(product.min_price)


class CatalogModelTests(CatalogData, TestCase):
    """Защита от случайного удаления, ограничения и переводы."""

    def test_category_and_probe_with_products_cannot_be_deleted(self):
        self.new_product()
        with self.assertRaises(ProtectedError):
            self.category.delete()
        with self.assertRaises(ProtectedError):
            self.probe.delete()

    def test_deleting_product_removes_its_variants_and_images(self):
        product = self.new_product()
        product.variants.create(weight=Decimal("2"))
        ProductImage.objects.create(product=product, image="products/x.jpg")
        product.delete()
        self.assertFalse(ProductVariant.objects.exists() or ProductImage.objects.exists())

    def test_size_is_unique_inside_a_product(self):
        from django.db import IntegrityError, transaction

        first, second = self.new_product("a"), self.new_product("b")
        first.variants.create(size="17", weight=Decimal("2"))
        second.variants.create(size="17", weight=Decimal("2"))  # у другого товара тот же размер можно
        with self.assertRaises(IntegrityError), transaction.atomic():
            first.variants.create(size="17", weight=Decimal("3"))

    def test_local_fields_follow_the_page_language(self):
        product = self.new_product(name_en="Ring", description="Описание")
        self.category.name_ky = "Шакектер"
        with translation.override("en"):
            self.assertEqual(product.name_local, "Ring")
            self.assertEqual(product.description_local, "Описание")  # перевода нет: русский текст
            self.assertEqual(self.category.name_local, "Кольца")
        with translation.override("ky"):
            self.assertEqual(self.category.name_local, "Шакектер")
            self.assertEqual(product.name_local, product.name)
        with translation.override("ru"):
            self.assertEqual(product.name_local, product.name)

    def test_attribute_value_is_shown_with_its_attribute(self):
        stone = Attribute.objects.create(name="Камень")
        value = AttributeValue.objects.create(attribute=stone, value="Фианит", value_en="Cubic zirconia")
        self.assertEqual(str(value), "Камень: Фианит")
        with translation.override("en"):
            self.assertEqual(value.value_local, "Cubic zirconia")

        product = self.new_product()
        product.attribute_values.add(value)
        self.assertEqual(list(value.products.all()), [product])


class CatalogChangeLogTests(CatalogData, TestCase):
    """Правки каталога в админке попадают в журнал изменений."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "pass")
        self.client.force_login(self.admin)

    def product_form(self, product=None, **changes):
        """Данные формы товара с таблицами вариантов и фото, как их отправляет админка."""
        variants = list(product.variants.all()) if product else []
        data = {
            "name": product.name if product else "Кольцо с фианитом", "slug": product.slug if product else "ring-new",
            "category": self.category.pk, "probe": self.probe.pk, "surcharge": "0", "is_active": "on",
            "variants-TOTAL_FORMS": len(variants), "variants-INITIAL_FORMS": len(variants), "variants-MIN_NUM_FORMS": 0, "variants-MAX_NUM_FORMS": 1000,
            "images-TOTAL_FORMS": 0, "images-INITIAL_FORMS": 0, "images-MIN_NUM_FORMS": 0, "images-MAX_NUM_FORMS": 1000,
        }
        for i, variant in enumerate(variants):
            data |= {f"variants-{i}-id": variant.pk, f"variants-{i}-product": product.pk, f"variants-{i}-size": variant.size,
                     f"variants-{i}-weight": variant.weight, f"variants-{i}-custom_price": variant.custom_price or "", f"variants-{i}-in_stock": "on"}
        return data | changes

    def updates(self):
        return {(log.object_label, log.field, log.old_value, log.new_value) for log in ChangeLog.objects.filter(action=ChangeLog.Action.UPDATE)}

    def test_product_with_variant_created_in_admin(self):
        data = self.product_form(**{"variants-TOTAL_FORMS": 1, "variants-0-size": "17", "variants-0-weight": "2", "variants-0-in_stock": "on"})
        response = self.client.post(reverse("admin:catalog_product_add"), data)
        self.assertEqual(response.status_code, 302, "форма товара не сохранилась")

        product = Product.objects.get()
        self.assertEqual(product.min_price, Decimal("10000.00"))
        created = {(log.object_label, log.changed_by) for log in ChangeLog.objects.filter(action=ChangeLog.Action.CREATE)}
        self.assertEqual(created, {("Кольцо с фианитом", self.admin), ("Кольцо с фианитом, 17", self.admin)})

    def test_variant_edit_inside_product_form_is_logged(self):
        product = self.new_product()
        product.variants.create(size="17", weight=Decimal("2"))

        response = self.client.post(
            reverse("admin:catalog_product_change", args=[product.pk]),
            self.product_form(product, **{"variants-0-weight": "2.5", "variants-0-custom_price": "13000"}),
        )
        self.assertEqual(response.status_code, 302, "форма товара не сохранилась")
        self.assertEqual(self.updates(), {
            ("Кольцо ring, 17", "Вес, г", "2.00", "2.50"),
            ("Кольцо ring, 17", "Своя цена, сом", "", "13000.00"),
        })

    def test_product_fields_and_attribute_values_are_logged(self):
        product = self.new_product()
        value = AttributeValue.objects.create(attribute=Attribute.objects.create(name="Камень"), value="Фианит")

        self.client.post(
            reverse("admin:catalog_product_change", args=[product.pk]),
            self.product_form(product, surcharge="500", attribute_values=[value.pk]),
        )
        self.assertEqual(self.updates(), {
            ("Кольцо ring", "Доплата, сом", "0.00", "500.00"),
            ("Кольцо ring", "Характеристики", "", "Камень: Фианит"),
        })

    def test_deleted_product_stays_in_the_journal(self):
        product = self.new_product()
        self.client.post(reverse("admin:catalog_product_delete", args=[product.pk]), {"post": "yes"})
        self.assertFalse(Product.objects.exists())
        self.assertTrue(ChangeLog.objects.filter(action=ChangeLog.Action.DELETE, object_label="Кольцо ring").exists())


class CatalogModeratorTests(CatalogData, TestCase):
    """Модератор после setup_roles работает с каталогом, но не с пользователями."""

    def setUp(self):
        super().setUp()
        call_command("setup_roles", verbosity=0)
        self.moder = User.objects.create_user("moder", password="pass", is_staff=True)
        self.moder.groups.add(Group.objects.get(name="Модераторы"))
        self.client.force_login(self.moder)

    def test_moderator_has_catalog_permissions(self):
        for perm in ["catalog.add_product", "catalog.change_product", "catalog.delete_product", "catalog.change_productvariant",
                     "catalog.add_productimage", "catalog.change_category", "catalog.add_attribute", "catalog.add_attributevalue"]:
            with self.subTest(perm):
                self.assertTrue(self.moder.has_perm(perm))

    def test_moderator_opens_catalog_pages(self):
        product = self.new_product()
        product.variants.create(size="17", weight=Decimal("2"))
        urls = [reverse("admin:catalog_product_changelist"), reverse("admin:catalog_category_changelist"),
                reverse("admin:catalog_attribute_changelist"), reverse("admin:catalog_product_add")]
        for url in urls:
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 200)

        # в форме товара модератору видны таблицы вариантов и фото
        response = self.client.get(reverse("admin:catalog_product_change", args=[product.pk]))
        self.assertContains(response, 'name="variants-0-weight"')
        self.assertContains(response, 'name="images-TOTAL_FORMS"')

    def test_catalog_is_in_the_sidebar(self):
        response = self.client.get(reverse("admin:index"))
        for name in ["admin:catalog_product_changelist", "admin:catalog_category_changelist", "admin:catalog_attribute_changelist"]:
            with self.subTest(name):
                self.assertContains(response, f'href="{reverse(name)}"')
        self.assertNotContains(response, f'href="{reverse("admin:auth_user_changelist")}"')


class CatalogAdminListTests(CatalogData, TestCase):
    """Списки каталога в админке: порядок перетаскиванием, ссылки на форму товара."""

    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("admin", "admin@example.com", "pass"))

    def test_new_categories_go_to_the_end(self):
        second = Category.objects.create(name="Серьги", slug="earrings")
        third = Category.objects.create(name="Цепи", slug="chains")
        self.assertEqual([self.category.order, second.order, third.order], [0, 1, 2])

    def test_images_are_ordered_inside_their_product(self):
        first, second = self.new_product("a"), self.new_product("b")
        orders = [ProductImage.objects.create(product=product, image="products/x.jpg").order for product in (first, first, second)]
        self.assertEqual(orders, [0, 1, 0])  # у второго товара счёт свой

    def test_category_list_is_sortable_by_dragging(self):
        response = self.client.get(reverse("admin:catalog_category_changelist"))
        self.assertContains(response, 'data-ordering-field="order"')

    def test_dragged_order_is_saved(self):
        second = Category.objects.create(name="Серьги", slug="earrings")
        # то, что отправляет список после перетаскивания «Серьги» на первое место и нажатия «Сохранить»
        data = {"form-TOTAL_FORMS": 2, "form-INITIAL_FORMS": 2, "form-MIN_NUM_FORMS": 0, "form-MAX_NUM_FORMS": 1000, "_save": "Сохранить",
                "form-0-id": second.pk, "form-0-order": 0, "form-0-is_active": "on",
                "form-1-id": self.category.pk, "form-1-order": 1, "form-1-is_active": "on"}
        self.client.post(reverse("admin:catalog_category_changelist"), data)
        self.assertEqual(list(Category.objects.values_list("name", flat=True)), ["Серьги", "Кольца"])

    def test_form_fields_do_not_shadow_html_form_properties(self):
        """Поле формы с именем свойства HTML-формы (attributes, action…) ломает скрипты админки:
        form.attributes начинает возвращать поле, и страница товара остаётся пустой."""
        from django.contrib import admin

        from . import models

        reserved = {"attributes", "action", "method", "target", "elements", "children", "style", "submit", "reset", "length", "classList", "dataset"}
        for model in (models.Product, models.Category, models.Attribute, models.AttributeValue, models.ProductVariant, models.ProductImage):
            names = {field.name for field in model._meta.get_fields()}
            with self.subTest(model.__name__):
                self.assertFalse(names & reserved)
        self.assertIn("attribute_values", admin.site._registry[models.Product].filter_horizontal)

    def test_product_opens_by_sku_and_by_name(self):
        product = self.new_product("a")
        url = reverse("admin:catalog_product_change", args=[product.pk])
        response = self.client.get(reverse("admin:catalog_product_changelist"))
        self.assertContains(response, f'href="{url}"', count=2)  # ссылка и в колонке артикула, и в колонке названия

    def test_product_list_does_not_query_per_row(self):
        url = reverse("admin:catalog_product_changelist")

        def queries_with(count, prefix):
            for i in range(count):
                self.new_product(f"{prefix}{i}").variants.create(size="17", weight=Decimal("2"))
            with CaptureQueriesContext(connection) as queries:
                self.client.get(url)
            return len(queries)

        self.client.get(url)  # первый запрос прогревает кеши Django
        self.assertEqual(queries_with(3, "a"), queries_with(10, "b"))  # товаров больше, запросов столько же

class SeedCatalogTests(TestCase):
    def test_second_run_creates_nothing(self):
        Probe.objects.create(metal="gold", fineness=585, price_per_gram=Decimal("5000"))
        call_command("seed_catalog", verbosity=0)
        counts = (Product.objects.count(), ProductVariant.objects.count(), Category.objects.count())
        self.assertEqual(counts[0], 25)

        call_command("seed_catalog", verbosity=0)
        self.assertEqual((Product.objects.count(), ProductVariant.objects.count(), Category.objects.count()), counts)

    def test_stops_without_probes(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_catalog", verbosity=0)
        self.assertFalse(Product.objects.exists())
