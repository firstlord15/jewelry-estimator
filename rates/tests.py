from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from django.contrib.auth.models import Group, Permission, User
from django.test import override_settings

from core.models import ChangeLog

from .models import Probe, QuickWeight


class RatesApiTests(TestCase):
    def setUp(self):
        Probe.objects.create(
            metal="gold", fineness=585, price_per_gram=Decimal("4800.50")
        )
        Probe.objects.create(
            metal="silver", fineness=925, price_per_gram=Decimal("155"), is_active=False
        )
        self.url = reverse("rates_api")

    def test_returns_only_active(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        rates = response.json()["rates"]
        self.assertEqual(len(rates), 1)
        self.assertEqual(rates[0]["fineness"], 585)

    def test_price_is_exact_string(self):
        rates = self.client.get(self.url).json()["rates"]
        self.assertEqual(rates[0]["price_per_gram"], "4800.50")

    def test_only_get_allowed(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)

    def test_labels_follow_lang_parameter(self):
        data = self.client.get(self.url, {"lang": "en"}).json()
        self.assertEqual(data["rates"][0]["metal_label"], "Gold")
        self.assertEqual(data["currency_label"], "som")

    def test_unknown_lang_is_ignored(self):
        response = self.client.get(self.url, {"lang": "xx"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rates"][0]["metal_label"], "Золото")

    def test_empty_when_no_probes(self):
        Probe.objects.all().delete()
        data = self.client.get(self.url).json()
        self.assertEqual(data["rates"], [])
        self.assertIsNone(data["updated_at"])

class IndexPageTests(TestCase):
    def test_index_opens(self):
        response = self.client.get(reverse("calculator"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Рассчитайте стоимость")

    def test_skeletons_shown_until_rates_load(self):
        response = self.client.get(reverse("calculator"))
        self.assertContains(response, 'class="chip skeleton"')
        self.assertContains(response, 'class="rate-row skeleton"', count=4)

    @override_settings(CALC_SHOW_QUANTITY=False)
    def test_quantity_hidden(self):
        response = self.client.get(reverse("calculator"))
        self.assertNotContains(response, 'id="qty"')
        self.assertContains(response, 'data-show-qty="0"')

    @override_settings(CALC_SHOW_QUANTITY=True)
    def test_quantity_shown(self):
        response = self.client.get(reverse("calculator"))
        self.assertContains(response, 'id="qty"')
        self.assertContains(response, 'data-show-qty="1"')


class QuickWeightsTests(TestCase):
    def setUp(self):
        # миграция заложила стандартный набор; для проверок начинаем с чистого листа
        QuickWeight.objects.all().delete()
        self.url = reverse("rates_api")

    def test_active_sorted_and_trimmed(self):
        QuickWeight.objects.create(grams=Decimal("10"))
        QuickWeight.objects.create(grams=Decimal("2.5"))
        QuickWeight.objects.create(grams=Decimal("7"), is_active=False)
        self.assertEqual(self.client.get(self.url).json()["quick_weights"], ["2.5", "10"])

    def test_empty_by_default(self):
        self.assertEqual(self.client.get(self.url).json()["quick_weights"], [])


class RatesChangeLogTests(TestCase):
    """Пробы, быстрые веса и пользователи в админке пишут в общий журнал изменений."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "pass")
        self.client.force_login(self.admin)

    def save_user(self, user, **changes):
        """Сохраняет форму пользователя в админке с текущими значениями и правками из changes."""
        url = reverse("admin:auth_user_change", args=[user.pk])
        form = self.client.get(url).context["adminform"].form
        data = {name: value for name, value in form.initial.items() if value not in (None, [], False)}
        data |= {"date_joined_0": user.date_joined.date().isoformat(), "date_joined_1": user.date_joined.strftime("%H:%M:%S")}
        data.pop("date_joined", None), data.pop("password", None), data.pop("last_login", None)
        data["groups"] = [group.pk for group in data.get("groups", [])]
        data["user_permissions"] = [perm.pk for perm in data.get("user_permissions", [])]
        response = self.client.post(url, data | changes)
        self.assertEqual(response.status_code, 302, "форма пользователя не сохранилась")

    def updates(self):
        return [(log.object_label, log.field, log.old_value, log.new_value) for log in ChangeLog.objects.filter(action=ChangeLog.Action.UPDATE)]

    def test_probe_created_in_admin(self):
        self.client.post(reverse("admin:rates_probe_add"), {"metal": "gold", "fineness": 585, "price_per_gram": "4800.50", "is_active": "on"})
        log = ChangeLog.objects.get()
        self.assertEqual((log.action, log.object_label, log.changed_by), (ChangeLog.Action.CREATE, "Золото 585", self.admin))

    def test_price_change_shows_old_and_new(self):
        probe = Probe.objects.create(metal="gold", fineness=585, price_per_gram=Decimal("4800.50"))
        url = reverse("admin:rates_probe_change", args=[probe.pk])

        # та же цена, записанная иначе («4800.5»): это не изменение
        self.client.post(url, {"metal": "gold", "fineness": 585, "price_per_gram": "4800.5", "is_active": "on"})
        self.assertFalse(ChangeLog.objects.exists())

        self.client.post(url, {"metal": "gold", "fineness": 585, "price_per_gram": "4900", "is_active": "on"})
        log = ChangeLog.objects.get()
        self.assertEqual((log.field, log.old_value, log.new_value), ("цена за 1 г, сом", "4800.50", "4900.00"))

    def test_probe_deleted_one_by_one_and_in_bulk(self):
        first = Probe.objects.create(metal="gold", fineness=585, price_per_gram=Decimal("4800"))
        Probe.objects.create(metal="gold", fineness=750, price_per_gram=Decimal("6000"))
        Probe.objects.create(metal="silver", fineness=925, price_per_gram=Decimal("155"))

        self.client.post(reverse("admin:rates_probe_delete", args=[first.pk]), {"post": "yes"})
        rest = list(Probe.objects.values_list("pk", flat=True))
        self.client.post(reverse("admin:rates_probe_changelist"), {"action": "delete_selected", "_selected_action": rest, "post": "yes"})

        self.assertFalse(Probe.objects.exists())
        labels = set(ChangeLog.objects.filter(action=ChangeLog.Action.DELETE).values_list("object_label", flat=True))
        self.assertEqual(labels, {"Золото 585", "Золото 750", "Серебро 925"})

    def test_quick_weight_is_logged(self):
        self.client.post(reverse("admin:rates_quickweight_add"), {"grams": "33", "is_active": "on"})
        self.assertEqual(ChangeLog.objects.get().object_label, "33 г")

    def test_user_created_and_edited_in_admin(self):
        self.client.post(reverse("admin:auth_user_add"), {"username": "moder", "usable_password": "true", "password1": "Str0ng-pass-123", "password2": "Str0ng-pass-123"})
        user = User.objects.get(username="moder")
        created = ChangeLog.objects.get()
        self.assertEqual((created.action, created.object_label), (ChangeLog.Action.CREATE, "moder"))

        self.save_user(user, is_staff="on")

        change = ChangeLog.objects.get(action=ChangeLog.Action.UPDATE)
        self.assertEqual((change.field, change.old_value, change.new_value), ("статус персонала", "False", "True"))

    def test_user_groups_are_logged(self):
        user = User.objects.create_user("moder")
        group = Group.objects.create(name="Модераторы")

        self.save_user(user, groups=[group.pk])
        self.assertEqual(self.updates(), [("moder", "группы", "", "Модераторы")])

        self.save_user(user, first_name="Айбек")  # группы не трогали: записи про них нет
        self.assertEqual([field for _, field, _, _ in self.updates()], ["имя", "группы"])

        self.save_user(user, groups=[])
        self.assertEqual(self.updates()[0], ("moder", "группы", "Модераторы", ""))

    def test_group_and_its_permissions_are_logged(self):
        perm = Permission.objects.get(content_type__app_label="rates", codename="view_probe")
        self.client.post(reverse("admin:auth_group_add"), {"name": "Модераторы", "permissions": [perm.pk]})
        group = Group.objects.get()

        created = ChangeLog.objects.get(action=ChangeLog.Action.CREATE)
        self.assertEqual(created.object_label, "Модераторы")
        ((label, field, old, new),) = self.updates()
        self.assertEqual((label, field, old), ("Модераторы", "права", ""))
        self.assertEqual(new, "Пробы: просмотр")  # понятное название вместо «Rates | проба | Can view проба»

        self.client.post(reverse("admin:auth_group_delete", args=[group.pk]), {"post": "yes"})
        self.assertTrue(ChangeLog.objects.filter(action=ChangeLog.Action.DELETE, object_label="Модераторы").exists())

    def test_permission_lists_use_readable_names(self):
        group = Group.objects.create(name="Модераторы")
        for url in [reverse("admin:auth_group_change", args=[group.pk]), reverse("admin:auth_user_change", args=[self.admin.pk])]:
            with self.subTest(url):
                response = self.client.get(url)
                self.assertContains(response, "Пробы: просмотр")
                self.assertContains(response, "Журнал изменений: просмотр")
                self.assertNotContains(response, "Can view")

    def test_password_change_is_logged_without_the_password(self):
        user = User.objects.create_user("moder", password="old-pass")
        url = reverse("admin:auth_user_password_change", args=[user.pk])

        self.client.post(url, {"usable_password": "true", "password1": "a", "password2": "b"})  # не совпали: не сохранено
        self.assertFalse(ChangeLog.objects.exists())

        self.client.post(url, {"usable_password": "true", "password1": "Str0ng-pass-123", "password2": "Str0ng-pass-123"})
        user.refresh_from_db()
        self.assertTrue(user.check_password("Str0ng-pass-123"))
        self.assertEqual(self.updates(), [("moder", "пароль", "", "изменён")])

    def test_own_profile_edit_is_logged(self):
        self.client.post(reverse("admin:rates_profile_change", args=[self.admin.pk]), {"first_name": "Админ", "last_name": "", "email": "admin@example.com"})
        self.assertEqual(self.updates(), [("admin", "имя", "", "Админ")])
