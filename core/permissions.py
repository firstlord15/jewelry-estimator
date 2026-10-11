from django.contrib.contenttypes.models import ContentType
from django.utils.text import capfirst

# Стандартные права Django: начало кода права → название действия
ACTIONS = {"view": "просмотр", "add": "добавление", "change": "изменение", "delete": "удаление"}


def permission_label(permission):
    """«Пробы: просмотр» вместо стандартного «Rates | проба | Can view проба»."""
    content_type = ContentType.objects.get_for_id(permission.content_type_id)  # из кеша, без запроса на каждое право
    model = content_type.model_class()
    kind = capfirst(model._meta.verbose_name_plural) if model else content_type.model

    action, _, model_name = permission.codename.partition("_")
    if action in ACTIONS and model_name == content_type.model:
        return f"{kind}: {ACTIONS[action]}"
    return f"{kind}: {permission.name}"  # нестандартное право: показываем его название как есть


class PermissionLabelsMixin:
    """Списки прав в формах пользователя и группы с понятными названиями."""

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        field = super().formfield_for_manytomany(db_field, request=request, **kwargs)
        if field is not None and db_field.name in ("permissions", "user_permissions"):
            field.label_from_instance = permission_label
        return field
