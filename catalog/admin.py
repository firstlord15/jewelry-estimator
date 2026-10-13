from django.contrib import admin
from unfold.admin import TabularInline

from core.admin_base import LoggedAdmin

from .models import Attribute, AttributeValue, Category, Product, ProductImage, ProductVariant


class VariantInline(TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("size", "weight", "auto_price", "custom_price", "in_stock")
    readonly_fields = ("auto_price",)

    @admin.display(description="Расчетная цена, сом")
    def auto_price(self, obj):
        return obj.calculated_price if obj.pk else "—"


class ImageInline(TabularInline):
    model = ProductImage
    extra = 0
    fields = ("image", "order")
    ordering_field = "order"
    hide_ordering_field = True


@admin.register(Product)
class ProductAdmin(LoggedAdmin):
    inlines = [VariantInline, ImageInline]

    # --- список товаров ---
    list_display = ("sku", "name", "category", "probe", "price_from", "views", "is_active")
    list_display_links = ("sku", "name")  # форма товара открывается и по артикулу, и по названию
    list_filter = ("category", "probe", "is_active")
    search_fields = ("name", "sku")
    list_select_related = ("category", "probe")

    # --- форма товара ---
    readonly_fields = ("sku", "views")
    prepopulated_fields = { "slug": ("name",) }
    filter_horizontal = ("attribute_values",)

    fieldsets = (
        (None, {"fields": ("sku", "name", "slug", "category", "probe", "surcharge", "description", "attribute_values", "views", "is_active")}),
        ("Кыргызча", {"classes": ["tab"], "fields": ("name_ky", "description_ky")}),
        ("English", {"classes": ["tab"], "fields": ("name_en", "description_en")}),
    )

    def get_queryset(self, request):
        # варианты одним запросом: иначе «Цена от» делает запрос на каждую строку списка
        return super().get_queryset(request).prefetch_related("variants")

    @admin.display(description="Цена от, сом")
    def price_from(self, obj):
        return obj.min_price or "—"


@admin.register(Category)
class CategoryAdmin(LoggedAdmin):
    list_display = ("name", "is_active")
    list_editable = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    exclude = ("order",)  # номер не вводят: новая категория встаёт в конец
    # Порядок меняют перетаскиванием строк в списке, затем «Сохранить» внизу
    ordering_field = "order"
    hide_ordering_field = True


class ValueInline(TabularInline):
    fields = ("value", "value_ky", "value_en", "is_quick", "order")
    ordering_field = "order"
    hide_ordering_field = True
    model = AttributeValue
    extra = 0


@admin.register(Attribute)
class AttributeAdmin(LoggedAdmin):
    inlines = [ValueInline]
    list_display = ("name", "is_filter", "is_searchable")
    list_editable = ("is_filter", "is_searchable")
    exclude = ("order",)
    ordering_field = "order"
    hide_ordering_field = True
