from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from django.test import override_settings
from .models import Probe


class RatesApiTests(TestCase):
    def setUp(self):
        Probe.objects.create(
            metal="gold", fineness=585, price_per_gram=Decimal("4800.50")
        )
        Probe.objects.create(
            metal="silver", fineness=925, price_per_gram=Decimal("155"), is_active=False
        )
        self.url = reverse("rates:api")

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

    def test_empty_when_no_probes(self):
        Probe.objects.all().delete()
        data = self.client.get(self.url).json()
        self.assertEqual(data["rates"], [])
        self.assertIsNone(data["updated_at"])

class IndexPageTests(TestCase):
    def test_index_opens(self):
        response = self.client.get(reverse("rates:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Расчёт стоимости")

    @override_settings(CALC_SHOW_QUANTITY=False)
    def test_quantity_hidden(self):
        response = self.client.get(reverse("rates:index"))
        self.assertNotContains(response, "js-qty")
        self.assertContains(response, 'data-show-qty="0"')

    @override_settings(CALC_SHOW_QUANTITY=True)
    def test_quantity_shown(self):
        response = self.client.get(reverse("rates:index"))
        self.assertContains(response, "js-qty")
        self.assertContains(response, 'data-show-qty="1"')