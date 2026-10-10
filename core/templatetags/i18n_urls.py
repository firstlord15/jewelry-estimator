from django import template
from django.urls import translate_url

register = template.Library()


@register.simple_tag(takes_context=True)
def url_for_language(context, lang_code):
    """Адрес текущей страницы на другом языке: /catalog/ → /en/catalog/."""
    return translate_url(context["request"].get_full_path(), lang_code)
