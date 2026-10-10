from django.contrib import admin
from django.shortcuts import redirect
from unfold.admin import ModelAdmin, TabularInline

from .models import Phone, SiteSettings


class PhoneInline(TabularInline):
    model = Phone
    extra = 0
    fields = ("label", "label_ky", "label_en", "number", "order")
    verbose_name_plural = "Телефоны (footer => первый в порядке)"


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
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
