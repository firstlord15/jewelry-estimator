from django.contrib import admin
from django.shortcuts import redirect
from django.utils.text import capfirst
from unfold.admin import ModelAdmin, TabularInline

from .models import Phone, SiteSettings, ChangeLog
from .admin_base import LoggedAdmin


class PhoneInline(TabularInline):
    model = Phone
    extra = 0
    fields = ("label", "label_ky", "label_en", "number", "order")
    verbose_name_plural = "Телефоны (footer => первый в порядке)"


@admin.register(SiteSettings)
class SiteSettingsAdmin(LoggedAdmin):
    inlines = [PhoneInline]

    # Тексты по языкам лежат во вкладках; пустой перевод на сайте заменяется русским текстом
    fieldsets = (
        (None, {"fields": ("name", "logo", "email")}),
        ("Мессенджеры и соцсети", {"fields": ("instagram", "whatsapp", "telegram")}),
        ("Русский", {"classes": ["tab"], "fields": ("address", "working_hours", "about")}),
        ("Кыргызча", {"classes": ["tab"], "fields": ("address_ky", "working_hours_ky", "about_ky")}),
        ("English", {"classes": ["tab"], "fields": ("address_en", "working_hours_en", "about_en")}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # Список из одной записи не нужен: сразу открываем форму
    def changelist_view(self, request, extra_context=None):
        return redirect("admin:core_sitesettings_change", SiteSettings.load().pk)


@admin.register(ChangeLog)
class ChangeLogAdmin(ModelAdmin):
    list_display = ("changed_at", "object_title", "action", "field", "old_value", "new_value", "changed_by")
    list_filter = ("action", "content_type", "changed_by")
    search_fields = ("object_label",)
    date_hierarchy = "changed_at"
    list_select_related = ("content_type", "changed_by")

    @admin.display(description="Объект", ordering="object_label")
    def object_title(self, obj):
        """«Пользователь: test», «Проба: Золото 585»: вид объекта и его название в одной колонке."""
        kind = capfirst(obj.content_type.name) if obj.content_type else ""
        # у «Настроек сайта» название совпадает с видом: не повторяем
        if not kind or kind.lower() == obj.object_label.lower():
            return obj.object_label
        return f"{kind}: {obj.object_label}"

    # Журнал только читают: записи создаёт core/services.py
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
