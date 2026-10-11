from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import translation

from .models import ChangeLog
from .permissions import permission_label

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


# ---------- Связи «многие ко многим» (группы, права) и события без значений ----------


@_in_russian
def m2m_values(obj):
    """Связи как списки названий: {поле: ["Модераторы", ...]}. Они сохраняются отдельно от объекта."""
    return {f: sorted(_item_label(item) for item in getattr(obj, f.name).all()) for f in obj._meta.many_to_many}


def _item_label(item):
    return permission_label(item) if isinstance(item, Permission) else str(item)


def log_m2m_changes(obj, before, user):
    """Сравнивает связи с тем, что было до сохранения (before из m2m_values), и пишет разницу."""
    for f, new in m2m_values(obj).items():
        old = before.get(f, [])
        if old != new:
            _log(obj, ChangeLog.Action.UPDATE, user, f.verbose_name, ", ".join(old), ", ".join(new))


def log_note(obj, user, field, new=""):
    """Запись без «было»: например «пароль: изменён», когда сами значения в журнал попадать не должны."""
    _log(obj, ChangeLog.Action.UPDATE, user, field, "", new)
