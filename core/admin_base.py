from unfold.admin import ModelAdmin

from .services import delete_logged, save_logged


class LoggedAdmin(ModelAdmin):
    def save_model(self, request, obj, form, change):
        save_logged(obj, request.user)

    def delete_model(self, request, obj):
        delete_logged(obj, request.user)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            delete_logged(obj, request.user)

    def save_formset(self, request, form, formset, change):
        for obj in formset.save(commit=False):
            save_logged(obj, request.user)
        for obj in formset.deleted_objects:
            delete_logged(obj, request.user)
        formset.save_m2m()