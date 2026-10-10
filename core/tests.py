from django.test import TestCase
from django.urls import reverse

from .models import SiteSettings
from django.conf import settings


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
    def test_pages_open(self):
        for name in ["home", "catalog", "cart", "favorites", "about", "contacts", "calculator"]:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_contacts_shows_all_phones(self):
        site = SiteSettings.load()
        site.phones.create(label="Главный", number="+996 555 123 456", order=1)
        site.phones.create(label="Второй", number="+996 700 000 000", order=2)

        response = self.client.get(reverse("contacts"))
        self.assertContains(response, "+996 555 123 456")
        self.assertContains(response, "+996 700 000 000")
        self.assertContains(response, "Второй")

    def test_language_switch_available(self):
        response = self.client.post(reverse("set_language"), {"language": "en", "next": "/"})
        self.assertRedirects(response, "/")


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