from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

MODERATORS_GROUP = "Модераторы"

# Что может модератор: (приложение, модель, действия). Пользователи и группы только у администратора
MODERATOR_PERMISSIONS = [
    ("rates", "probe", ["view", "add", "change", "delete"]),
    ("rates", "quickweight", ["view", "add", "change", "delete"]),
    ("core", "sitesettings", ["view", "change"]),
    ("core", "phone", ["view", "add", "change", "delete"]),
    ("core", "changelog", ["view"]),  # журнал только читают
]


class Command(BaseCommand):
    help = "Создаёт или обновляет группу «Модераторы» и выдаёт ей права из списка MODERATOR_PERMISSIONS"

    def handle(self, *args, **options):
        perms, missing = [], []
        for app, model, actions in MODERATOR_PERMISSIONS:
            for action in actions:
                codename = f"{action}_{model}"
                perm = Permission.objects.filter(content_type__app_label=app, codename=codename).first()
                if perm:
                    perms.append(perm)
                else:
                    missing.append(f"{app}.{codename}")

        if missing:
            raise CommandError(
                f"Не найдены права: {', '.join(missing)}. "
                "Сначала выполните: python manage.py migrate"
            )

        group, created = Group.objects.get_or_create(name=MODERATORS_GROUP)
        group.permissions.set(perms)  # лишние права, выданные раньше, снимаются

        status = "создана" if created else "обновлена"
        self.stdout.write(self.style.SUCCESS(
            f"Группа «{MODERATORS_GROUP}» {status}, прав: {len(perms)}"
        ))
