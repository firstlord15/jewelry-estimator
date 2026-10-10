import re

from django.db import models


class SiteSettings(models.Model):
    """Контакты и тексты сайта. Запись всегда одна (pk=1), правится в админке."""

    name = models.CharField("Название", max_length=255, default="Gold Store")
    logo = models.ImageField("Логотип", upload_to="site_settings/", blank=True)
    email = models.EmailField("Почта", blank=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    working_hours = models.CharField("Часы работы", max_length=255, blank=True)
    instagram = models.URLField("Instagram", blank=True)
    whatsapp = models.URLField("WhatsApp", blank=True, help_text="Например, https://wa.me/996555123456")
    telegram = models.URLField("Telegram", blank=True)
    about = models.TextField("О нас", blank=True)

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
    number = models.CharField("Номер", max_length=30)
    order = models.PositiveIntegerField("Порядок", default=0)

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