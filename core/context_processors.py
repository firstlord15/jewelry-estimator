from django.conf import settings

from .models import SiteSettings


def site(request):
    """Настройки сайта из админки и адрес сайта из .env: доступны во всех шаблонах."""
    site_settings = SiteSettings.load()
    phones = list(site_settings.phones.all())
    return {
        "site_settings": site_settings,
        "phones": phones,
        "main_phone": phones[0] if phones else None,
        "SITE_NAME": site_settings.name or settings.SITE_NAME,
        "SITE_URL": settings.SITE_URL,
    }
