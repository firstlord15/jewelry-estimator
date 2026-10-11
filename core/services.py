from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import translation

from .models import ChangeLog

# Не пишем в журнал: пароль (даже хеш), время входа и дату регистрации. Дату форма админки
# пересохраняет без микросекунд, и без исключения каждая правка пользователя давала бы ложную запись
SKIP_FIELDS = {"password", "last_login", "date_joined"}


def _in_russian(func):
    """Журнал всегда на языке сайта по умолчанию, на каком бы языке ни была открыта страница."""

    def wrapper(*args, **kwargs):
        with translation.override(settings.LANGUAGE_CODE):
            return func(*args, **kwargs)

    return wrapper


@_in_russian
def _values(obj):
    """Значения полей как текст: {поле: "значение"}. Служебные поля пропускаем."""
    result = {}
    for field in obj._meta.concrete_fields:
        if field.name in SKIP_FIELDS:
            continue

        if field.primary_key or getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue

        value = getattr(obj, f"get_{field.name}_display")() if field.choices else getattr(obj, field.name)
        result[field] = "" if value is None else str(value)

    return result


@_in_russian
def _label(obj):
    return str(obj)[:255]


@_in_russian
def _log(obj, action, user, field="", old="", new="", label=None):
    ChangeLog.objects.create(
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk, object_label=label or _label(obj),
        action=action, field=str(field), old_value=old, new_value=new, changed_by=user,
    )


@transaction.atomic
def save_logged(obj, user):
    is_new = obj._state.adding
    if not is_new:
        stored = type(obj).objects.get(pk=obj.pk)
        before = _values(stored)
        # название до правки: при переименовании test → test2 запись относится к «test»
        label = _label(stored)
    obj.save()
    obj.refresh_from_db() # чтобы сравнить значения в том виде, в котором они сохранены в базе
    if is_new:
        _log(obj, ChangeLog.Action.CREATE, user)
        return
    for f, new in _values(obj).items():
        if before[f] != new:
            _log(obj, ChangeLog.Action.UPDATE, user, f.verbose_name, before[f], new, label=label)


@transaction.atomic
def delete_logged(obj, user):
    _log(obj, ChangeLog.Action.DELETE, user)
    obj.delete()
