from django.test import TestCase
from django.urls import reverse
from django.utils import translation

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