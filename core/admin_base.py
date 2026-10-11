from unfold.admin import ModelAdmin

from .services import delete_logged, log_m2m_changes, m2m_values, save_logged


class LoggedAdmin(ModelAdmin):
    """Админка, которая пишет в журнал изменений создание, правки и удаление своих объектов."""

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

    # Группы и права (многие ко многим) Django сохраняет здесь, уже после самого объекта
    def save_related(self, request, form, formsets, change):
        obj = form.instance
        before = m2m_values(obj) if change else {}
        super().save_related(request, form, formsets, change)
        log_m2m_changes(obj, before, request.user)
