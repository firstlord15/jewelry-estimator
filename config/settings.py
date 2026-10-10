from pathlib import Path
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# env
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

UNFOLD = {
    # --- название и логотип ---
    "SITE_TITLE": env.str("SITE_NAME"),          # вкладка браузера
    "SITE_HEADER": env.str("SITE_NAME"),         # заголовок в боковой панели
    "SITE_SUBHEADER": _("Управление"),   # подпись под ним (необязательно)
    "SITE_URL": "/",                     # куда ведёт ссылка «на сайт»
    "SITE_SYMBOL": "diamond",            # иконка Material Symbols, пока нет логотипа
    # Иконка (логотип) рядом с названием в боковой панели и на странице входа.
    # Для светлой и тёмной темы админки свой цвет; файлы лежат в static/img/
    "SITE_ICON": {
        "light": lambda request: static("img/admin-logo-light.svg"),
        "dark": lambda request: static("img/admin-logo-dark.svg"),
    },
    "SITE_FAVICONS": [
        {"rel": "icon", "type": "image/svg+xml", "href": lambda request: static("img/favicon.svg")},
    ],

    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    # "LOGIN": {"image": lambda request: static("img/login-bg.jpg")},

    # --- золотой акцент (основной цвет кнопок, ссылок, выбранных пунктов) ---
    "COLORS": {
        "primary": {
            "50": "oklch(98.7% .026 102.212)",
            "100": "oklch(97.3% .071 103.193)",
            "200": "oklch(94.5% .129 101.54)",
            "300": "oklch(90.5% .182 98.111)",
            "400": "oklch(85.2% .199 91.936)",
            "500": "oklch(79.5% .184 86.047)",
            "600": "oklch(68.1% .162 75.834)",
            "700": "oklch(55.4% .135 66.442)",
            "800": "oklch(47.6% .114 61.907)",
            "900": "oklch(42.1% .095 57.708)",
            "950": "oklch(28.6% .066 53.813)",
        },
    },

    # --- боковое меню ---
    "SIDEBAR": {
        "show_search": True,             # поиск по меню
        "show_all_applications": False,  # показывать только то, что перечислено ниже
        "navigation": [
            {
                "title": _("Курс и калькулятор"),
                "separator": True,
                "items": [
                    {
                        "title": _("Пробы"),
                        "icon": "paid",
                        "link": reverse_lazy("admin:rates_probe_changelist"),
                        "permission": lambda request: request.user.has_perm("rates.view_probe"),
                    },
                    {
                        "title": _("Быстрые веса"),
                        "icon": "scale",
                        "link": reverse_lazy("admin:rates_quickweight_changelist"),
                        "permission": lambda request: request.user.has_perm("rates.view_quickweight"),
                    },
                    {
                        "title": _("История изменений"),
                        "icon": "history",
                        "link": reverse_lazy("admin:rates_pricechange_changelist"),
                        "permission": lambda request: request.user.has_perm("rates.view_pricechange"),
                    },
                ],
            },
            {
                "title": _("Сайт"),
                "separator": True,
                "items": [
                    {
                        "title": _("Настройки сайта"),
                        "icon": "settings",
                        "link": reverse_lazy("admin:core_sitesettings_changelist"),
                        "permission": lambda request: request.user.has_perm("core.view_sitesettings"),
                    },
                ],
            },
            {
                "title": _("Пользователи"),
                "separator": True,
                "items": [
                    {
                        "title": _("Мой профиль"),
                        "icon": "person",
                        "link": reverse_lazy("admin:rates_profile_changelist"),
                    },
                    {
                        "title": _("Пользователи"),
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                    {
                        "title": _("Группы и права"),
                        "icon": "admin_panel_settings",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                        "permission": lambda request: request.user.is_superuser,
                    },
                ],
            },
        ],
    },
}

# Application definition
INSTALLED_APPS = [
    'unfold',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'rates',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # раздаёт статику в продакшене, сразу после SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # язык по cookie/заголовку, после сессий и до CommonMiddleware
    'core.middleware.AdminLanguageMiddleware',  # принудительно русский язык в админке, после LocaleMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site',
                'django.template.context_processors.i18n',
            ],
        },
    },
]

STATICFILES_DIRS = [BASE_DIR / "static"]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    'default': env.db("DATABASE_URL")
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = env.str("LANGUAGE_CODE")

TIME_ZONE = env.str("TIME_ZONE")

USE_I18N = True

# Языки сайта. Название выводится в переключателе языка
LANGUAGES = [
    ("ru", "Русский"),
    ("ky", "Кыргызча"),
    ("en", "English"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

USE_TZ = True

SITE_NAME = env.str("SITE_NAME", default="Gold Store")
SITE_URL = env.str("SITE_URL", default="http://127.0.0.1:8000")

CALC_SHOW_QUANTITY = env.bool("CALC_SHOW_QUANTITY", default=False)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # сюда складывает файлы collectstatic

# Загруженные файлы (фото товаров): пока на диске, позже можно переключить на S3 через django-storages
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    # со сжатием, но без манифеста с хешами: манифест ломает тесты и страницы, пока не выполнен collectstatic
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'