from django.db import transaction
from .models import PriceChange, Probe


def _log(probe, action, user, old_price=None, new_price=None):
    PriceChange.objects.create(
        probe=probe,
        probe_label=str(probe),
        action=action,
        old_price=old_price,
        new_price=new_price,
        changed_by=user,
    )


@transaction.atomic
def save_probe(probe, user):
    """Сохраняет пробу и записывает в историю создание или смену цены."""
    if probe.pk is None:
        probe.save()
        _log(probe, PriceChange.Action.CREATED, user, new_price=probe.price_per_gram)
        return

    old_price = (
        Probe.objects.filter(pk=probe.pk)
        .values_list("price_per_gram", flat=True)
        .first()
    )
    probe.save()
    if old_price != probe.price_per_gram:
        _log(probe, PriceChange.Action.PRICE, user, old_price, probe.price_per_gram)


@transaction.atomic
def delete_probe(probe, user):
    """Записывает удаление в историю, затем удаляет пробу."""
    _log(probe, PriceChange.Action.DELETED, user, old_price=probe.price_per_gram)
    probe.delete()