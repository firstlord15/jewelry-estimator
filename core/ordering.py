from django.db import models
from django.db.models import Max


class AutoOrderMixin(models.Model):
    """Новая запись встаёт в конец списка: её order = последний + 1.

    Дальше порядок меняют перетаскиванием в админке (ordering_field у Unfold), номера вручную не пишут.
    order_scope: имя ссылки, внутри которой свой счёт (фото считаются в пределах товара).
    """

    order_scope = None

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self._state.adding and not self.order:
            siblings = type(self)._default_manager.all()
            if self.order_scope:
                siblings = siblings.filter(**{self.order_scope: getattr(self, f"{self.order_scope}_id")})
            last = siblings.aggregate(last=Max("order"))["last"]
            self.order = 0 if last is None else last + 1
        super().save(*args, **kwargs)
