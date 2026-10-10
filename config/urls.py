from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from rates import views as rates_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/rates/", rates_views.rates_api, name="rates_api"),
]

# Страницы сайта: русский без префикса (/catalog/), остальные с ним (/ky/catalog/, /en/catalog/)
urlpatterns += i18n_patterns(
    path("", include("core.urls")),
    path("", include("rates.urls")),
    prefix_default_language=False,
)

# В разработке отдаём загруженные файлы сами; в продакшене их раздаёт nginx или хранилище
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
