from django.utils.translation import get_language


class Localized:
    """Значение поля на языке страницы.

    Русский текст лежит в самом поле (address), переводы в соседних (address_ky, address_en).
    Пустой перевод заменяется русским текстом.

        address_local = Localized("address")
    """

    def __init__(self, field):
        self.field = field

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        lang = (get_language() or "").split("-")[0]
        return getattr(obj, f"{self.field}_{lang}", "") or getattr(obj, self.field)
