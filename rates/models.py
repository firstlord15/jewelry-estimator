from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Metal(models.TextChoices):
    GOLD = "gold", _("Золото")
    SILVER = "silver", _("Серебро")


class Probe(models.Model):
    """Проба металла и её текущая цена за грамм."""

    metal = models.CharField("металл", max_length=10, choices=Metal.choices)
    fineness = models.PositiveSmallIntegerField(
        "проба",
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Например: 585, 750, 925",
    )
    price_per_gram = models.DecimalField(
        "цена за 1 г, сом",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    is_active = models.BooleanField(
        "показывать на сайте",
        default=True,
        help_text="Снимите галочку, чтобы скрыть пробу, не удаляя её",
    )
    updated_at = models.DateTimeField("обновлено", auto_now=True)

    class Meta:
        verbose_name = "проба"
        verbose_name_plural = "пробы"
        ordering = ["metal", "-fineness"]
        constraints = [
            models.UniqueConstraint(
                fields=["metal", "fineness"],
                name="unique_metal_fineness",
            )
        ]

    def __str__(self):
        return f"{self.get_metal_display()} {self.fineness}"


class QuickWeight(models.Model):
    """Быстрый вес: кнопка «5 г» под полем веса в калькуляторе."""

    grams = models.DecimalField(
        "вес, г",
        max_digits=8,
        decimal_places=2,
        unique=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Например: 1, 2.5, 10",
    )
    is_active = models.BooleanField(
        "показывать на сайте",
        default=True,
        help_text="Снимите галочку, чтобы скрыть кнопку, не удаляя её",
    )

    class Meta:
        verbose_name = "быстрый вес"
        verbose_name_plural = "быстрые веса"
        ordering = ["grams"]

    def __str__(self):
        return f"{self.grams.normalize():f} г"


class PriceChange(models.Model):
    """Запись в истории: кто, когда и что сделал с пробой."""

    class Action(models.TextChoices):
        CREATED = "created", "Создана"
        PRICE = "price", "Изменена цена"
        DELETED = "deleted", "Удалена"

    probe = models.ForeignKey(
        Probe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="changes",
        verbose_name="проба",
    )
    probe_label = models.CharField("проба", max_length=50)
    action = models.CharField("действие", max_length=10, choices=Action.choices)
    old_price = models.DecimalField(
        "было", max_digits=12, decimal_places=2, null=True, blank=True
    )
    new_price = models.DecimalField(
        "стало", max_digits=12, decimal_places=2, null=True, blank=True
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="кто",
    )
    changed_at = models.DateTimeField("когда", auto_now_add=True)

    class Meta:
        verbose_name = "запись истории"
        verbose_name_plural = "история изменений"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.probe_label}: {self.get_action_display()}"


class Profile(User):
    """Тот же пользователь, но в разделе, где видно только себя."""

    class Meta:
        proxy = True
        verbose_name = "мой профиль"
        verbose_name_plural = "мой профиль"