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


@admin.register(Product)
class ProductAdmin(LoggedAdmin):
    inlines = [VariantInline, ImageInline]

    # --- список товаров ---
    list_display = ("sku", "name", "category", "probe", "price_from", "is_active")
    list_filter = ("category", "probe", "is_active")
    search_fields = ("name", "sku")
    list_select_related = ("category", "probe")

    # --- форма товара ---
    readonly_fields = ("sku",)
    prepopulated_fields = { "slug": ("name",) }
    filter_horizontal = ("attributes",)

    fieldsets = (
        (None, {"fields": ("sku", "name", "slug", "category", "probe", "surcharge", "description", "attributes", "is_active")}),
        ("Кыргызча", {"classes": ["tab"], "fields": ("name_ky", "description_ky")}),
        ("English", {"classes": ["tab"], "fields": ("name_en", "description_en")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request)

    @admin.display(description="Цена от, сом")
    def price_from(self, obj):
        return obj.min_price or "—"

@admin.register(Category)
class CategoryAdmin(LoggedAdmin):
    list_display = ("name", "order", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = { "slug": ("name",) }

class ValueInline(TabularInline):
    model = AttributeValue
    extra = 0
    fields = ("value", "value_ky", "value_en")

@admin.register(Attribute)
class AttributeAdmin(LoggedAdmin):
    inlines = [ValueInline]
    list_display = ("name", "order")
    list_editable = ("order",) 