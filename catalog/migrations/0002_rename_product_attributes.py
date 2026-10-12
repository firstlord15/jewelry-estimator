from django.db import migrations


class Migration(migrations.Migration):
    """Поле формы «attributes» ломало страницу товара в админке: имя совпадает со свойством HTML-формы."""

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="product",
            old_name="attributes",
            new_name="attribute_values",
        ),
    ]
