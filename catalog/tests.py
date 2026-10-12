from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from rates.models import Probe

from .models import Category, Product, ProductImage


class CatalogAdminListTests(TestCase):
    """Списки каталога в админке: порядок перетаскиванием, ссылки на форму товара."""

    def setUp(self):
        self.client.force_login(User.objects.create_superuser("admin", "admin@example.com", "pass"))
        self.probe = Probe.objects.create(metal="gold", fineness=585, price_per_gram=Decimal("5000"))
        self.category = Category.objects.create(name="Кольца", slug="rings")

    def new_product(self, slug):
        return Product.objects.create(category=self.category, probe=self.probe, name=f"Кольцо {slug}", slug=slug)

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
