from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User

from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from .models import PriceChange, Probe, Profile, QuickWeight
from .services import delete_probe, save_probe

from django.urls import reverse
from django.utils.html import format_html

admin.site.site_header = "Ювелирный калькулятор"
admin.site.site_title = "Управление"
admin.site.index_title = "Курс металлов и пользователи"


@admin.register(Probe)
class ProbeAdmin(ModelAdmin):
    list_display = ("__str__", "price_per_gram", "is_active", "updated_at")
    list_editable = ("price_per_gram", "is_active")
    list_filter = ("metal", "is_active")

    def save_model(self, request, obj, form, change):
        save_probe(obj, request.user)

    def delete_model(self, request, obj):
        delete_probe(obj, request.user)

    def delete_queryset(self, request, queryset):
        # Массовое удаление через «Действия» в списке
        for probe in queryset:
            delete_probe(probe, request.user)


@admin.register(QuickWeight)
class QuickWeightAdmin(ModelAdmin):
    list_display = ("__str__", "is_active")
    list_editable = ("is_active",)
    list_filter = ("is_active",)


@admin.register(PriceChange)
class PriceChangeAdmin(ModelAdmin):
    list_display = (
        "changed_at", "probe_label", "action", "old_price", "new_price", "changed_by",
    )
    list_filter = ("action", "changed_by")
    search_fields = ("probe_label",)
    date_hierarchy = "changed_at"
    list_select_related = ("changed_by",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

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


# Стандартные User/Group заменяем версиями под Unfold: иначе нет кнопок «Добавить» и т.п.
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass
