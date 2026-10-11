from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User

from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from .models import Probe, Profile, QuickWeight

from django.urls import reverse
from django.utils.html import format_html

from core.admin_base import LoggedAdmin


@admin.register(Probe)
class ProbeAdmin(LoggedAdmin):
    list_display = ("__str__", "price_per_gram", "is_active", "updated_at")
    list_editable = ("price_per_gram", "is_active")
    list_filter = ("metal", "is_active")


@admin.register(QuickWeight)
class QuickWeightAdmin(LoggedAdmin):
    list_display = ("__str__", "is_active")
    list_editable = ("is_active",)
    list_filter = ("is_active",)


@admin.register(Profile)
class ProfileAdmin(ModelAdmin):
    fields = ("username", "first_name", "last_name", "email", "password_link")
    readonly_fields = ("username", "password_link")
    list_display = ("username", "first_name", "last_name", "email")

    @admin.display(description="Пароль")
    def password_link(self, obj):
        return format_html(
            '<a class="button" href="{}">Сменить пароль</a>',
            reverse("admin:password_change"),
        )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(pk=request.user.pk)

    def _is_self(self, request, obj):
        return request.user.is_staff and (obj is None or obj.pk == request.user.pk)

    def has_module_permission(self, request):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return self._is_self(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._is_self(request, obj)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Стандартные User/Group заменяем версиями под Unfold
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
# BaseUserAdmin первым: иначе форма создания теряет поле логина. Сохранение и удаление берутся из LoggedAdmin
class UserAdmin(BaseUserAdmin, LoggedAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass