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

// Цена: поля и ползунок с двумя ручками связаны в обе стороны. Запрос уходит, когда ручку отпустили:
// это событие change, оно всплывает до формы, и HTMX отправляет её. Пока ручку тянут (input), запросов нет
document.querySelectorAll("[data-price-range]").forEach((box) => {
    const low = Number(box.dataset.min);
    const high = Number(box.dataset.max);
    const slider = box.querySelector(".price-range__slider");
    const field = { min: box.querySelector('[name="price_min"]'), max: box.querySelector('[name="price_max"]') };
    const range = { min: box.querySelector('[data-range="min"]'), max: box.querySelector('[data-range="max"]') };
    const edge = { min: low, max: high };

    // Золотой отрезок между ручками. Левая ручка наверху, если она в правой половине:
    // иначе две ручки в одной точке справа не развести — сверху лежит правая, а ей дальше вправо некуда
    const paint = () => {
        const percent = (value) => ((value - low) / (high - low)) * 100 + "%";
        slider.style.setProperty("--from", percent(range.min.value));
        slider.style.setProperty("--to", percent(range.max.value));
        range.min.style.zIndex = Number(range.min.value) > (low + high) / 2 ? 2 : "";
    };

    // Поле → ручка. Пусто или не число — ручка у края. Число за границей ползунок сам прижмёт к краю
    const fromField = (side) => {
        const value = parseFloat(field[side].value.replace(",", ".").replace(/\s/g, ""));
        range[side].value = Number.isFinite(value) ? value : edge[side];
    };

    // Ручка → поле. Левая не заходит за правую и наоборот. Ручка у края — поле пустое: фильтра по цене нет
    const fromRange = (side) => {
        const other = side === "min" ? "max" : "min";
        if (Number(range.min.value) > Number(range.max.value)) range[side].value = range[other].value;
        field[side].value = Number(range[side].value) === edge[side] ? "" : range[side].value;
        paint();
    };

    for (const side of ["min", "max"]) {
        range[side].addEventListener("input", () => fromRange(side));
        field[side].addEventListener("input", () => {
            fromField(side);
            paint();
        });
        fromField(side);
    }
    paint();
});

// Фильтры на телефоне: панель открывается поверх страницы в <dialog>. Esc и затемнение закрывают её сами
// (Esc — браузер, затемнение — проверка ниже). На компьютере кнопки открытия не видно, и код не срабатывает
const filtersDialog = document.querySelector("#filters-dialog");
if (filtersDialog) {
    document.querySelector("[data-open-filters]")?.addEventListener("click", () => filtersDialog.showModal());
    filtersDialog.querySelectorAll("[data-close-filters]").forEach((button) => button.addEventListener("click", () => filtersDialog.close()));

    // клик по затемнению: цель — сам <dialog>, а не что-то внутри формы
    filtersDialog.addEventListener("click", (event) => {
        if (event.target === filtersDialog) filtersDialog.close();
    });
}
