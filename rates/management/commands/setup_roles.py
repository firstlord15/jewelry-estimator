from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

MODERATORS_GROUP = "Модераторы"

MODERATOR_PERMISSIONS = [
    "view_probe",
    "add_probe",
    "change_probe",
    "delete_probe",
    "view_pricechange",
    "view_quickweight",
    "add_quickweight",
    "change_quickweight",
    "delete_quickweight",
]


class Command(BaseCommand):
    help = "Создаёт или обновляет группу «Модераторы» с правами на пробы и быстрые веса"

    def handle(self, *args, **options):
        perms = Permission.objects.filter(
            content_type__app_label="rates",
            codename__in=MODERATOR_PERMISSIONS,
        )

        found = set(perms.values_list("codename", flat=True))
        missing = set(MODERATOR_PERMISSIONS) - found
        if missing:
            raise CommandError(
                f"Не найдены права: {', '.join(sorted(missing))}. "
                "Сначала выполните: python manage.py migrate"
            )

        group, created = Group.objects.get_or_create(name=MODERATORS_GROUP)
        group.permissions.set(perms)

        status = "создана" if created else "обновлена"
        self.stdout.write(self.style.SUCCESS(
            f"Группа «{MODERATORS_GROUP}» {status}, прав: {perms.count()}"
        ))