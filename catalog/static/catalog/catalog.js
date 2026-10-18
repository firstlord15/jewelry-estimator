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

document.querySelectorAll("[data-filter-search]").forEach((search) => {
    const group = search.closest(".filter-group");

    search.addEventListener("input", () => {
        const text = search.value.trim().toLocaleLowerCase();
        group.querySelectorAll(".filter-option").forEach((option) => {
            const name = option.querySelector(".filter-option__name").textContent.toLocaleLowerCase();
            option.hidden = !name.includes(text);
        });

        // совпадения могут оказаться и среди значений под «Показать ещё»
        const more = group.querySelector(".filter-more");
        if (more && text) more.open = true;
    });

    // Поле не фильтр: его change не должен отправлять форму через HTMX, а Enter — перезагружать страницу
    search.addEventListener("change", (event) => event.stopPropagation());
    search.addEventListener("keydown", (event) => {
        if (event.key === "Enter") event.preventDefault();
    });
});
