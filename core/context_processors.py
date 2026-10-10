from django.conf import settings

from .models import SiteSettings


def site(request):
    """Настройки сайта из админки и адрес сайта из .env: доступны во всех шаблонах."""
    site_settings = SiteSettings.load()
    return {
        "site_settings": site_settings,
        "SITE_NAME": site_settings.name or settings.SITE_NAME,
        "SITE_URL": settings.SITE_URL,
    }
