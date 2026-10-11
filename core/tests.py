from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from django.conf import settings
from django.contrib.auth.models import User

from .models import ChangeLog, Phone, SiteSettings
from .services import delete_logged, save_logged


class SiteSettingsTests(TestCase):
    def test_load_keeps_single_record(self):
        first = SiteSettings.load()
        SiteSettings(name="Другая запись").save()  # save() всё равно пишет в pk=1
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(SiteSettings.load().pk, first.pk)


class FooterTests(TestCase):
    def test_name_and_contacts_from_settings(self):
        site = SiteSettings.load()
        site.name = "Тестовый магазин"
        site.phones.create(label="Главный", number="+996 555 123 456", order=1)
        site.phones.create(label="Второй", number="+996 700 000 000", order=2)
        site.telegram = "https://t.me/example"
        site.save()

        response = self.client.get(reverse("calculator"))
        self.assertContains(response, "Тестовый магазин")
        self.assertContains(response, 'href="tel:+996555123456"')
        self.assertContains(response, 'href="https://t.me/example"')
        self.assertNotContains(response, 'aria-label="Instagram"')  # пустая ссылка не выводится


class PagesTests(TestCase):
    def test_pages_open_in_all_languages(self):
        for lang in ["ru", "ky", "en"]:
            for name in ["home", "catalog", "cart", "favorites", "about", "contacts", "calculator"]:
                with self.subTest(lang=lang, name=name):
                    with translation.override(lang):
                        url = reverse(name)  # /catalog/, /ky/catalog/, /en/catalog/
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, f'<html lang="{lang}">')

    def test_default_language_has_no_prefix(self):
        with translation.override("ru"):  # явно: язык мог остаться от запроса в другом тесте
            self.assertEqual(reverse("catalog"), "/catalog/")
        with translation.override("en"):
            self.assertEqual(reverse("catalog"), "/en/catalog/")
            self.assertEqual(reverse("rates_api"), "/api/rates/")  # API вне языковых адресов

    def test_header_marks_current_page(self):
        for name in ["catalog", "favorites", "cart", "calculator"]:
            with self.subTest(name):
                response = self.client.get(reverse(name))
                self.assertContains(response, f'href="{reverse(name)}" aria-current="page"', count=1)
        # страницы не из шапки: точки нет
        self.assertNotContains(self.client.get(reverse("about")), 'aria-current="page"')

    def test_contacts_shows_all_phones(self):
        site = SiteSettings.load()
        site.phones.create(label="Главный", number="+996 555 123 456", order=1)
        site.phones.create(label="Второй", number="+996 700 000 000", order=2)

        response = self.client.get(reverse("contacts"))
        self.assertContains(response, "+996 555 123 456")
        self.assertContains(response, "+996 700 000 000")
        self.assertContains(response, "Второй")

    def test_language_links_point_to_same_page(self):
        # с любой страницы, даже если в cookie остался другой язык
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "ky"
        for url in ["/catalog/", "/ky/catalog/", "/en/catalog/"]:
            with self.subTest(url):
                response = self.client.get(url)
                self.assertContains(response, 'href="/catalog/" hreflang="ru"')
                self.assertContains(response, 'href="/ky/catalog/" hreflang="ky"')
                self.assertContains(response, 'href="/en/catalog/" hreflang="en"')

    def test_pages_are_translated(self):
        self.assertContains(self.client.get("/en/catalog/"), "Catalog")
        self.assertContains(self.client.get("/ky/cart/"), "Себет")
        self.assertContains(self.client.get("/catalog/"), "Каталог")


class ContentTranslationTests(TestCase):
    """Тексты из админки: свой перевод в отдельном поле, без перевода показывается русский."""

    def setUp(self):
        site = SiteSettings.load()
        site.address = "Бишкек, Ибраимова 113"
        site.address_en = "113 Ibraimov St, Bishkek"
        site.about = "Мы продаём украшения"
        site.about_ky = "Биз жасалгаларды сатабыз"
        site.save()
        site.phones.create(label="Поддержка", label_en="Support", number="+996 555 123 456")

    def test_russian_page_shows_russian(self):
        response = self.client.get("/contacts/")
        self.assertContains(response, "Поддержка")
        self.assertContains(response, "Бишкек, Ибраимова 113")
        self.assertNotContains(response, "Support")

    def test_translated_in_english(self):
        response = self.client.get("/en/contacts/")
        self.assertContains(response, "Support")
        self.assertContains(response, "113 Ibraimov St, Bishkek")
        self.assertNotContains(response, "Поддержка")

    def test_empty_translation_falls_back_to_russian(self):
        response = self.client.get("/ky/contacts/")  # кыргызские название и адрес не заполнены
        self.assertContains(response, "Поддержка")
        self.assertContains(response, "Бишкек, Ибраимова 113")

    def test_about_page(self):
        self.assertContains(self.client.get("/ky/about/"), "Биз жасалгаларды сатабыз")
        self.assertContains(self.client.get("/en/about/"), "Мы продаём украшения")  # английского нет

    def test_admin_form_has_language_fields(self):
        from django.contrib.auth.models import User

        self.client.force_login(User.objects.create_superuser("admin", "admin@example.com", "pass"))
        response = self.client.get(reverse("admin:core_sitesettings_change", args=[1]))
        for field in ["address_ky", "about_en", "phones-0-label_en"]:
            self.assertContains(response, f'name="{field}"')


class SiteSettingsAdminTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.client.force_login(User.objects.create_superuser("admin", "admin@example.com", "pass"))

    def test_changelist_redirects_to_form(self):
        response = self.client.get(reverse("admin:core_sitesettings_changelist"))
        self.assertRedirects(response, reverse("admin:core_sitesettings_change", args=[1]))

    def test_cannot_add(self):
        response = self.client.get(reverse("admin:core_sitesettings_add"))
        self.assertEqual(response.status_code, 403)


class AdminLanguageMiddlewareTests(TestCase):
    def test_admin_is_russian_even_with_kyrgyz_cookie(self):
        from django.contrib.auth.models import User

        self.client.force_login(User.objects.create_superuser("admin", "admin@example.com", "pass"))
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "ky"
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, 'lang="ru"')


class ChangeLogServiceTests(TestCase):
    """Журнал изменений: save_logged и delete_logged из core/services.py."""

    def setUp(self):
        self.user = User.objects.create_user("moder", password="pass")
        self.site = SiteSettings.load()

    def new_phone(self, **kwargs):
        phone = Phone(site=self.site, label="Поддержка", number="+996 555 123 456", **kwargs)
        save_logged(phone, self.user)
        return phone

    def test_create_makes_one_record(self):
        phone = self.new_phone()
        log = ChangeLog.objects.get()
        self.assertEqual(log.action, ChangeLog.Action.CREATE)
        self.assertEqual(log.object_label, "+996 555 123 456")
        self.assertEqual(log.object_id, phone.pk)
        self.assertEqual(log.content_type.model, "phone")
        self.assertEqual(log.changed_by, self.user)

    def test_update_records_each_changed_field(self):
        phone = self.new_phone()
        phone.label = "Магазин"
        phone.order = 5
        save_logged(phone, self.user)

        changes = {log.field: (log.old_value, log.new_value) for log in ChangeLog.objects.filter(action=ChangeLog.Action.UPDATE)}
        self.assertEqual(changes, {"Название": ("Поддержка", "Магазин"), "Порядок": ("0", "5")})

    def test_save_without_changes_makes_no_record(self):
        phone = self.new_phone()
        save_logged(phone, self.user)
        save_logged(Phone.objects.get(pk=phone.pk), self.user)
        self.assertEqual(ChangeLog.objects.count(), 1)  # только создание

    def test_delete_keeps_label_after_object_is_gone(self):
        phone = self.new_phone()
        delete_logged(phone, self.user)

        self.assertFalse(Phone.objects.exists())
        log = ChangeLog.objects.get(action=ChangeLog.Action.DELETE)
        self.assertEqual(log.object_label, "+996 555 123 456")

    def test_record_survives_user_deletion(self):
        self.new_phone()
        self.user.delete()
        self.assertIsNone(ChangeLog.objects.get().changed_by)

    def test_password_and_last_login_are_never_logged(self):
        from django.utils import timezone

        target = User.objects.create_user("buyer", password="old-pass")
        target.set_password("new-pass")
        target.last_login = timezone.now()
        target.email = "buyer@example.com"
        save_logged(target, self.user)

        logs = ChangeLog.objects.all()
        self.assertEqual([log.field for log in logs], ["адрес электронной почты"])
        for log in logs:
            self.assertNotIn("pbkdf2", log.old_value + log.new_value)

    def test_values_are_logged_in_russian_whatever_the_page_language(self):
        from rates.models import Probe

        probe = Probe(metal="gold", fineness=585, price_per_gram="4800")
        with translation.override("en"):
            save_logged(probe, self.user)
            probe.metal = "silver"
            save_logged(probe, self.user)

        self.assertEqual(ChangeLog.objects.get(action=ChangeLog.Action.CREATE).object_label, "Золото 585")
        change = ChangeLog.objects.get(action=ChangeLog.Action.UPDATE)
        self.assertEqual((change.field, change.old_value, change.new_value), ("металл", "Золото", "Серебро"))


class ChangeLogAdminTests(TestCase):
    """Журнал в админке: правки настроек попадают в него, а сам он только для чтения."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "pass")
        self.client.force_login(self.admin)

    def settings_form(self, **changes):
        """Данные формы «Настройки сайта» с текущими значениями и таблицей телефонов."""
        site = SiteSettings.load()
        data = {f.name: getattr(site, f.name) or "" for f in SiteSettings._meta.concrete_fields if f.name not in ("id", "logo")}
        phones = list(site.phones.all())
        data |= {"phones-TOTAL_FORMS": len(phones), "phones-INITIAL_FORMS": len(phones), "phones-MIN_NUM_FORMS": 0, "phones-MAX_NUM_FORMS": 1000}
        for i, phone in enumerate(phones):
            data |= {f"phones-{i}-id": phone.pk, f"phones-{i}-site": site.pk, f"phones-{i}-label": phone.label,
                     f"phones-{i}-label_ky": phone.label_ky, f"phones-{i}-label_en": phone.label_en,
                     f"phones-{i}-number": phone.number, f"phones-{i}-order": phone.order}
        return data | changes

    def post_settings(self, **changes):
        response = self.client.post(reverse("admin:core_sitesettings_change", args=[1]), self.settings_form(**changes))
        self.assertEqual(response.status_code, 302, "форма настроек не сохранилась")

    def test_settings_change_is_logged_with_user(self):
        self.post_settings(address="Бишкек, Ибраимова 113")
        log = ChangeLog.objects.get()
        self.assertEqual((log.field, log.old_value, log.new_value), ("Адрес", "", "Бишкек, Ибраимова 113"))
        self.assertEqual(log.changed_by, self.admin)

    def test_phone_rows_are_logged(self):
        phone = SiteSettings.load().phones.create(label="Поддержка", number="+996 555 123 456")

        self.post_settings(**{"phones-0-number": "+996 700 000 000"})
        change = ChangeLog.objects.get(action=ChangeLog.Action.UPDATE)
        self.assertEqual((change.field, change.old_value, change.new_value), ("Номер", "+996 555 123 456", "+996 700 000 000"))

        self.post_settings(**{"phones-0-DELETE": "on"})
        self.assertFalse(Phone.objects.filter(pk=phone.pk).exists())
        self.assertEqual(ChangeLog.objects.filter(action=ChangeLog.Action.DELETE).count(), 1)

    def test_list_names_object_with_its_kind(self):
        user = User.objects.create_user("test2")
        save_logged(user, self.admin)  # ничего не изменилось, записи нет
        user.email = "test2@example.com"
        save_logged(user, self.admin)

        user.username = "test3"
        save_logged(user, self.admin)
        self.post_settings(address="Бишкек")

        response = self.client.get(reverse("admin:core_changelog_changelist"))
        # при переименовании запись относится к прежнему названию
        self.assertContains(response, "Пользователь: test2", count=2)
        self.assertNotContains(response, "Пользователь: test3")
        # название совпадает с видом объекта: без повтора
        self.assertNotContains(response, "Настройки сайта: Настройки сайта")

    def test_journal_is_read_only(self):
        log = ChangeLog.objects.create(object_label="Проба", action=ChangeLog.Action.CREATE)
        self.assertEqual(self.client.get(reverse("admin:core_changelog_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:core_changelog_add")).status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:core_changelog_change", args=[log.pk]), {"object_label": "x"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:core_changelog_delete", args=[log.pk]), {"post": "yes"}).status_code, 403)
        self.assertTrue(ChangeLog.objects.filter(pk=log.pk, object_label="Проба").exists())


class ModeratorRoleTests(TestCase):
    """Команда setup_roles: что модератору можно в админке и что нельзя."""

    def setUp(self):
        from django.contrib.auth.models import Group
        from django.core.management import call_command

        call_command("setup_roles", verbosity=0)
        self.group = Group.objects.get(name="Модераторы")
        self.moder = User.objects.create_user("moder", password="pass", is_staff=True)
        self.moder.groups.add(self.group)
        self.client.force_login(self.moder)

    def test_group_permissions(self):
        perms = {f"{p.content_type.app_label}.{p.codename}" for p in self.group.permissions.select_related("content_type")}
        self.assertLessEqual({"rates.change_probe", "core.change_sitesettings", "core.add_phone", "core.view_changelog"}, perms)
        self.assertFalse(perms & {"core.change_changelog", "core.delete_changelog", "core.delete_sitesettings", "auth.view_user", "auth.change_group"})

    def test_command_can_run_twice_and_drops_extra_permissions(self):
        from django.contrib.auth.models import Permission
        from django.core.management import call_command

        self.group.permissions.add(Permission.objects.get(codename="delete_user"))
        call_command("setup_roles", verbosity=0)
        self.assertFalse(self.group.permissions.filter(codename="delete_user").exists())

    def test_moderator_pages(self):
        allowed = ["admin:rates_probe_changelist", "admin:rates_quickweight_changelist", "admin:core_changelog_changelist"]
        for name in allowed:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:core_sitesettings_change", args=[1])).status_code, 200)

        for name in ["admin:auth_user_changelist", "admin:auth_group_changelist"]:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_moderator_change_is_logged_under_their_name(self):
        from rates.models import Probe

        probe = Probe.objects.create(metal="gold", fineness=585, price_per_gram="4800")
        self.client.post(reverse("admin:rates_probe_change", args=[probe.pk]), {"metal": "gold", "fineness": 585, "price_per_gram": "4900", "is_active": "on"})
        self.assertEqual(ChangeLog.objects.get().changed_by, self.moder)
