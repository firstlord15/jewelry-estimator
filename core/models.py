import re

from django.db import models
from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from .localized import Localized


class SiteSettings(models.Model):
    """Контакты и тексты сайта. Запись всегда одна (pk=1), правится в админке.

    Тексты, которые вводятся в админке, переводятся там же: рядом с русским полем лежат _ky и _en.
    В шаблонах берём *_local: значение на языке страницы.
    """

    name = models.CharField("Название", max_length=255, default="Gold Store")
    logo = models.ImageField("Логотип", upload_to="site_settings/", blank=True)
    email = models.EmailField("Почта", blank=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    address_ky = models.CharField("Адрес (кыргызча)", max_length=255, blank=True)
    address_en = models.CharField("Адрес (English)", max_length=255, blank=True)
    working_hours = models.CharField("Часы работы", max_length=255, blank=True)
    working_hours_ky = models.CharField("Часы работы (кыргызча)", max_length=255, blank=True)
    working_hours_en = models.CharField("Часы работы (English)", max_length=255, blank=True)
    instagram = models.URLField("Instagram", blank=True)
    whatsapp = models.URLField("WhatsApp", blank=True, help_text="Например, https://wa.me/996555123456")
    telegram = models.URLField("Telegram", blank=True)
    about = models.TextField("О нас", blank=True)
    about_ky = models.TextField("О нас (кыргызча)", blank=True)
    about_en = models.TextField("О нас (English)", blank=True)

    address_local = Localized("address")
    working_hours_local = Localized("working_hours")
    about_local = Localized("about")

    class Meta:
        verbose_name = verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return "Настройки сайта"

    def save(self, *args, **kwargs):
        self.pk = 1  # всегда одна запись
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

class Phone(models.Model):
    """Телефонный номер для контактов сайта."""
    site = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name="phones")
    label = models.CharField("Название", max_length=255, blank=True, help_text="Например, «Контакт-центр»")
    label_ky = models.CharField("Название (кыргызча)", max_length=255, blank=True)
    label_en = models.CharField("Название (English)", max_length=255, blank=True)
    number = models.CharField("Номер", max_length=30)
    order = models.PositiveIntegerField("Порядок", default=0)

    label_local = Localized("label")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Телефон"
        verbose_name_plural = "Телефоны"

    def __str__(self):
        return self.number

    @property
    def tel(self):
        """Номер в формате для ссылки tel: (только цифры и +)"""
        return re.sub(r"[^\d+]", "", self.number)


class ChangeLog(models.Model):
    """Запись журнала: кто, когда и что изменил. Создаётся только через core/services.py."""

    class Action(models.TextChoices):
        CREATE = "create", "Создано"
        UPDATE = "update", "Изменено"
        DELETE = "delete", "Удалено"

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, verbose_name="Раздел")
    object_id = models.PositiveBigIntegerField("ID записи", null=True)
    object_label = models.CharField("Название записи", max_length=255)
    action = models.CharField("Действие", max_length=10, choices=Action.choices)
    field = models.CharField("Поле", max_length=255, blank=True)
    old_value = models.TextField("Старое значение", blank=True)
    new_value = models.TextField("Новое значение", blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name="Пользователь")
    changed_at = models.DateTimeField("Дата и время", auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Запись журнала изменений"
        verbose_name_plural = "Журнал изменений"