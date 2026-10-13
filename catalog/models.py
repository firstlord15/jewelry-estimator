from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import DecimalField, F, Min, Q
from django.db.models.functions import Coalesce, Round
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit

from core.localized import Localized
from core.ordering import AutoOrderMixin

MAX_IMAGE_SIZE_MB = 10


def validate_image_size(image):
    if image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Файл больше {MAX_IMAGE_SIZE_MB} МБ. Уменьшите фото и загрузите снова.")


class ProductQuerySet(models.QuerySet):
    def visible(self):
        """Только то, что видит покупатель."""
        return self.filter(is_active=True, category__is_active=True)

    def with_price(self):
        """Добавляет price_from: цену «от» среди вариантов в наличии, посчитанную в базе."""
        variant_price = Coalesce(
            F("variants__custom_price"),
            Round(F("variants__weight") * F("probe__price_per_gram") + F("surcharge"), 2),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
        return self.annotate(price_from=Min(variant_price, filter=Q(variants__in_stock=True)))


class Category(AutoOrderMixin, models.Model):
    """Категория каталога: «Кольца», «Серьги». Без вложенности."""

    name = models.CharField("Название", max_length=255)
    name_ky = models.CharField("Название (кыргызча)", max_length=255, blank=True)
    name_en = models.CharField("Название (English)", max_length=255, blank=True)
    banner = models.ImageField("Баннер", upload_to="categories/", blank=True, validators=[validate_image_size])
    banner_wide = ImageSpecField(
        source="banner",
        processors=[ResizeToFill(1600, 500)],
        format="WEBP",
        options={"quality": 85}, 
    )
    slug = models.SlugField("Адрес", unique=True, help_text="Часть адреса страницы: /catalog/rings/")
    order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Показывать на сайте", default=True)

    name_local = Localized("name")

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Attribute(AutoOrderMixin, models.Model):
    """Характеристика товара, которую заводят модераторы: «Камень», «Цвет металла»."""

    name = models.CharField("Название", max_length=255)
    name_ky = models.CharField("Название (кыргызча)", max_length=255, blank=True)
    name_en = models.CharField("Название (English)", max_length=255, blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    is_filter = models.BooleanField("Показывать в фильтре каталога", default=True)
    is_searchable = models.BooleanField("Показывать поле поиска", default=False)

    name_local = Localized("name")

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Характеристика"
        verbose_name_plural = "Характеристики"

    def __str__(self):
        return self.name


class AttributeValue(AutoOrderMixin, models.Model):
    """Значение характеристики: «Фианит» у «Камня»."""

    order_scope = "attribute"

    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name="values", verbose_name="Характеристика")
    value = models.CharField("Значение", max_length=255)
    value_ky = models.CharField("Значение (кыргызча)", max_length=255, blank=True)
    value_en = models.CharField("Значение (English)", max_length=255, blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)
    is_quick = models.BooleanField("Быстрый фильтр", default=False, help_text="Показывать кнопкой над товарами")

    value_local = Localized("value")

    class Meta:
        ordering = ["attribute", "order", "value"]
        verbose_name = "Значение характеристики"
        verbose_name_plural = "Значения характеристик"
        constraints = [
            models.UniqueConstraint(fields=["attribute", "value"], name="unique_attribute_value"),
        ]

    def __str__(self):
        return f"{self.attribute}: {self.value}"  # так значение видно в форме товара и в журнале


class Product(models.Model):
    """Товар. Цена считается у каждого варианта: от текущего курса пробы, веса и доплаты."""

    SKU_START = 100_000

    sku = models.PositiveIntegerField("Артикул", unique=True, editable=False, null=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products", verbose_name="Категория")
    probe = models.ForeignKey(
        "rates.Probe", on_delete=models.PROTECT, related_name="products", verbose_name="Проба",
        help_text="От пробы зависят металл и цена за грамм",
    )
    
    name = models.CharField("Название", max_length=255)
    name_ky = models.CharField("Название (кыргызча)", max_length=255, blank=True)
    name_en = models.CharField("Название (English)", max_length=255, blank=True)
    description = models.TextField("Описание", blank=True)
    description_ky = models.TextField("Описание (кыргызча)", blank=True)
    description_en = models.TextField("Описание (English)", blank=True)
    views = models.PositiveIntegerField("Просмотры", default=0, editable=False)
    slug = models.SlugField("Адрес", unique=True, help_text="Часть адреса страницы товара")
    surcharge = models.DecimalField(
        "Доплата, сом", max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("0"))], help_text="За работу и камни: прибавляется к цене металла",
    )
    
    # Не «attributes»: поле формы с таким именем подменяет встроенное свойство form.attributes,
    # и скрипты админки (Alpine, htmx) падают — страница товара остаётся пустой
    attribute_values = models.ManyToManyField(
        AttributeValue, blank=True, related_name="products", verbose_name="Характеристики"
    )
    
    is_active = models.BooleanField(
        "Показывать на сайте", default=True, help_text="Снимите галочку, чтобы скрыть товар, не удаляя его"
    )

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    name_local = Localized("name")
    description_local = Localized("description")

    objects = ProductQuerySet.as_manager()  # Product.objects.visible().with_price()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.sku is None:
            self.sku = self.SKU_START + self.pk
            super().save(update_fields=["sku"])

    @property
    def min_price(self):
        """Цена «от X сом»: самая низкая среди вариантов в наличии. None, если в наличии ничего нет."""
        prices = [variant.price for variant in self.variants.all() if variant.in_stock]
        return min(prices, default=None)


class ProductVariant(models.Model):
    """Вариант товара: размер меняет вес, а вес меняет цену.

    Цена по умолчанию расчётная и следует за курсом пробы. Если вписать свою цену, действует она;
    очистили поле (или поставили 0) — цена снова считается сама.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants", verbose_name="Товар")
    size = models.CharField("Размер", max_length=50, blank=True, help_text="«17», «45 см»; пусто, если размер один")
    weight = models.DecimalField(
        "Вес, г", max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    custom_price = models.DecimalField(
        "Своя цена, сом", max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Оставьте пустым, чтобы цена считалась сама: вес × цена за грамм + доплата",
    )
    in_stock = models.BooleanField("В наличии", default=True)

    class Meta:
        ordering = ["product", "weight"]
        verbose_name = "Вариант товара"
        verbose_name_plural = "Варианты товара"
        constraints = [
            models.UniqueConstraint(fields=["product", "size"], name="unique_product_size"),
        ]

    def __str__(self):
        return f"{self.product}, {self.size}" if self.size else str(self.product)

    def save(self, *args, **kwargs):
        if not self.custom_price:  # 0 значит то же, что пусто: своей цены нет
            self.custom_price = None
        super().save(*args, **kwargs)

    @property
    def calculated_price(self):
        """Вес × текущая цена за грамм + доплата, до тыйынов (два знака), как в калькуляторе."""
        total = self.weight * self.product.probe.price_per_gram + self.product.surcharge
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def price(self):
        """Цена варианта в сомах: своя, если она вписана, иначе расчётная."""
        return self.custom_price if self.custom_price is not None else self.calculated_price


class ProductImage(AutoOrderMixin, models.Model):
    """Фото товара. Оригинал хранится как есть, миниатюры в WebP создаются при первом показе."""

    order_scope = "product"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", verbose_name="Товар")
    image = models.ImageField("Фото", upload_to="products/", validators=[validate_image_size])
    order = models.PositiveIntegerField("Порядок", default=0, help_text="Фото с наименьшим номером — обложка")

    thumb = ImageSpecField(source="image", processors=[ResizeToFill(400, 400)], format="WEBP", options={"quality": 80})
    large = ImageSpecField(source="image", processors=[ResizeToFit(1200, 1200)], format="WEBP", options={"quality": 85})

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Фото товара"
        verbose_name_plural = "Фото товара"

    def __str__(self):
        return f"{self.product}: фото {self.order}"
