from django.conf import settings


def site(request):
    """Название и адрес сайта из .env: доступны во всех шаблонах как SITE_NAME и SITE_URL."""
    return {"SITE_NAME": settings.SITE_NAME, "SITE_URL": settings.SITE_URL}
