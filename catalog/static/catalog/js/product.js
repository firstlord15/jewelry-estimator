"use strict";

// Страница товара. Цену сервер кладёт в data-price уже отформатированной: здесь только подстановка

// Смена размера: цена и «Нет в наличии»
document.querySelectorAll('input[name="variant"]').forEach((radio) =>
    radio.addEventListener("change", () => {
        document.querySelector("#price").textContent = radio.dataset.price;
        document.querySelector("#stock").hidden = radio.dataset.stock === "1";
    }),
);

// Галерея: нажатие на миниатюру показывает это фото крупно
document.querySelectorAll(".product__thumb").forEach((thumb) =>
    thumb.addEventListener("click", () => {
        document.querySelector("#gallery-main").src = thumb.dataset.large;
        document.querySelectorAll(".product__thumb").forEach((other) => other.removeAttribute("aria-current"));
        thumb.setAttribute("aria-current", "true");
    }),
);
