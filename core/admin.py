from django.contrib import admin
from django.shortcuts import redirect
from unfold.admin import ModelAdmin, TabularInline

from .models import Phone, SiteSettings


class PhoneInline(TabularInline):
    model = Phone
    extra = 0
    can_delete = True
    fields = ("label", "number", "order")
    verbose_name_plural = "Телефоны (footer => первый в порядке)"
@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    inlines = [PhoneInline]

    fieldsets = (
        (None, {"fields": ("name", "logo", "about")}),
        ("Контакты", {"fields": ("email", "address", "working_hours")}),
        ("Мессенджеры и соцсети", {"fields": ("instagram", "whatsapp", "telegram")}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # Список из одной записи не нужен: сразу открываем форму
    def changelist_view(self, request, extra_context=None):
        return redirect("admin:core_sitesettings_change", SiteSettings.load().pk)
