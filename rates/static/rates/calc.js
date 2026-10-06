"use strict";

(() => {
  const API_URL = "/api/rates/";
  const STORAGE_KEY = "jewelry-calc-items";
  const SHOW_QTY = document.body.dataset.showQty === "1";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let itemsRendered = false;
  const itemNodes = new WeakMap(); // изделие -> его блок на странице; блоки пересоздаются, изделия остаются

  const state = {
    rates: [],
    currency: "сом",
    items: [],
    active: null, // изделие, чья проба подсвечена в таблице курса
    boardMetal: null, // металл, показанный в таблице курса
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const money = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
  const formatMoney = (value) => `${money.format(value)} ${state.currency}`;
  const findRate = (id) => state.rates.find((rate) => rate.id === id);
  const pricePerGram = (rate) => Number(rate.price_per_gram);
  const defaultProbeId = () => state.rates[0]?.id ?? null;

  function createElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // «3,5» и «3.5» — одно и то же; пустое, отрицательное и мусор — ноль
  function parseNumber(value) {
    const n = parseFloat(String(value).replace(",", ".").replace(/\s/g, ""));
    return Number.isFinite(n) && n > 0 ? n : 0;
  }

  // ---------- Сохранение блоков в браузере ----------

  function loadItems() {
    try {
      const data = JSON.parse(localStorage.getItem(STORAGE_KEY));
      return Array.isArray(data) && data.length ? data : null;
    } catch {
      return null;
    }
  }

  function saveItems() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.items));
    } catch {
      // приватный режим или запрет cookie: просто не сохраняем
    }
  }

  function newItem() {
    return { probeId: defaultProbeId(), grams: "", qty: "1" };
  }

  // ---------- Металлы и кнопки ----------

  const setPressed = (button, pressed) => button.setAttribute("aria-pressed", String(pressed));
  const metalOf = (probeId) => findRate(probeId)?.metal;
  // [[metal, label], ...] без повторов, в порядке прихода из API
  const metals = () => [...new Map(state.rates.map((rate) => [rate.metal, rate.metal_label]))];

  function createButton(className, text, dataset = {}) {
    const button = createElement("button", className, text);
    button.type = "button";
    Object.assign(button.dataset, dataset);
    return button;
  }

  // ---------- Табло курса ----------

  function initBoardMetals() {
    $("#board-metals").replaceChildren(
      ...metals().map(([metal, label]) => {
        const button = createButton("segment", label, { metal });
        button.addEventListener("click", () => {
          state.boardMetal = metal;
          syncBoard();
        });
        return button;
      }),
    );
  }

  // Строки выбранного металла; проба активного изделия подсвечена
  function syncBoard() {
    state.boardMetal ??= metalOf(state.active?.probeId) ?? state.rates[0]?.metal ?? null;

    for (const button of $$("#board-metals .segment")) {
      setPressed(button, button.dataset.metal === state.boardMetal);
    }

    const rows = state.rates
      .filter((rate) => rate.metal === state.boardMetal)
      .map((rate) => {
        const row = createElement("div", "rate-row");
        row.dataset.metal = rate.metal;
        row.classList.toggle("is-active", rate.id === state.active?.probeId);
        row.append(createElement("span", "", rate.fineness), createElement("span", "", `${money.format(pricePerGram(rate))} ${state.currency}`));
        return row;
      });
    $("#board").replaceChildren(...rows);
  }

  function setActive(item) {
    state.active = item;
    state.boardMetal = metalOf(item.probeId) ?? state.boardMetal;
    syncBoard();
  }

  // ---------- Блоки изделий ----------

  // Калькулятор, итог и курс меняют размер и место скачком: при добавлении и удалении изделия
  // и когда раскладка зависит от их числа. Плавно ведём каждый блок из старого вида в новый.
  // Пока идёт анимация:
  // - содержимое обрезается и прижимается к верху, чтобы шапка («Рассчитайте стоимость», «+») не уезжала
  //   вместе с центрированием, пока высота рамки меняется;
  // - строки и колонки сетки заморожены в итоговых размерах, иначе анимируемая высота одного блока
  //   пересчитывала бы строки и сдвигала соседей
  let layoutAnimations = [];

  function animateLayout(panels, before) {
    if (reduceMotion.matches) return;

    const layout = $(".layout");
    const after = panels.map((panel) => panel.getBoundingClientRect()); // все замеры до старта первой анимации
    const { gridTemplateColumns, gridTemplateRows } = getComputedStyle(layout);

    const animations = panels.flatMap((panel, index) => {
      const [from, to] = [before[index], after[index]];
      const [dx, dy] = [from.left - to.left, from.top - to.top];
      const resized = Math.abs(from.width - to.width) >= 1 || Math.abs(from.height - to.height) >= 1;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1 && !resized) return [];

      const start = { transform: `translate(${dx}px, ${dy}px)`, width: `${from.width}px`, height: `${from.height}px` };
      const end = { transform: "none", width: `${to.width}px`, height: `${to.height}px` };

      // Меняется и место по вертикали, и ширина: сначала спускаем блок и только потом растягиваем.
      // Если он поднимается, наоборот: сначала меняем ширину, потом поднимаем. Так он не наезжает на соседей
      const twoSteps = Math.abs(dy) >= 1 && (Math.abs(dx) >= 1 || resized);
      const step = { easing: "ease-out" };
      const keyframes = !twoSteps
        ? [start, end]
        : dy > 0
          ? [{ ...start, ...step }, { transform: `translate(0px, ${dy}px)`, width: end.width, height: end.height, ...step }, end]
          : [{ ...start, ...step }, { transform: `translate(${dx}px, 0px)`, width: start.width, height: start.height, ...step }, end];

      panel.style.overflow = "hidden";
      panel.style.justifyContent = "flex-start";
      const animation = panel.animate(keyframes, { duration: twoSteps ? 320 : 200, easing: twoSteps ? "linear" : "ease-out" });
      animation.onfinish = animation.oncancel = () => {
        panel.style.overflow = "";
        panel.style.justifyContent = "";
      };
      return [animation];
    });

    if (!animations.length) return;
    Object.assign(layout.style, { gridTemplateColumns, gridTemplateRows });
    layoutAnimations = animations;
    // если анимацию прервала новая, сетку разморозит уже она
    Promise.allSettled(animations.map((animation) => animation.finished)).then(() => {
      if (layoutAnimations === animations) Object.assign(layout.style, { gridTemplateColumns: "", gridTemplateRows: "" });
    });
  }

  // Остальные изделия при удалении или добавлении съезжают на новое место плавно, а не прыгают
  function animateItems(before) {
    if (reduceMotion.matches) return;

    for (const item of state.items) {
      const from = before.get(item);
      const node = itemNodes.get(item);
      const dy = from ? from.top - node.getBoundingClientRect().top : 0;
      if (Math.abs(dy) >= 1) node.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 200, easing: "ease-out" });
    }
  }

  // Показывает в блоке изделия текущее состояние: металл, пробу, вес, кнопку очистки
  function syncItem(item, node) {
    const metal = metalOf(item.probeId);
    if (metal) node.dataset.metal = metal;

    for (const segment of $$(".segment", node)) setPressed(segment, segment.dataset.metal === metal);
    for (const chip of $$(".js-probes .chip", node)) {
      chip.hidden = chip.dataset.metal !== metal;
      setPressed(chip, Number(chip.dataset.id) === item.probeId);
    }
    for (const chip of $$("[data-grams]", node)) setPressed(chip, parseNumber(item.grams) === Number(chip.dataset.grams));
    $(".js-clear", node).hidden = item.grams === "";
  }

  // Блок изделия из шаблона: значения из state и обработчики полей
  function createItemNode(item) {
    const node = $("#item-template").content.firstElementChild.cloneNode(true);
    itemNodes.set(item, node);
    const grams = $(".js-grams", node);
    const qty = $(".js-qty", node);
    const remove = $(".js-remove", node);

    // Проба могла быть удалена или скрыта, пока человека не было на сайте
    if (!findRate(item.probeId)) item.probeId = defaultProbeId();

    const update = () => {
      syncItem(item, node);
      updateTotals();
    };
    const chooseProbe = (id) => {
      item.probeId = id;
      update();
      setActive(item);
    };
    const setGrams = (value) => {
      item.grams = value;
      grams.value = value;
      update();
    };

    $(".js-metals", node).append(
      ...metals().map(([metal, label]) => {
        const segment = createButton("segment", label, { metal });
        segment.addEventListener("click", () => {
          if (metalOf(item.probeId) === metal) return setActive(item);
          chooseProbe(state.rates.find((rate) => rate.metal === metal).id);
        });
        return segment;
      }),
    );

    $(".js-probes", node).append(
      ...state.rates.map((rate) => {
        const chip = createButton("chip", rate.fineness, { id: rate.id, metal: rate.metal });
        chip.addEventListener("click", () => chooseProbe(rate.id));
        return chip;
      }),
    );

    for (const chip of $$("[data-grams]", node)) {
      chip.addEventListener("click", () => setGrams(chip.dataset.grams));
    }

    grams.value = item.grams;
    if (qty) qty.value = item.qty;
    remove.disabled = state.items.length === 1;

    grams.addEventListener("input", () => setGrams(grams.value));
    $(".js-clear", node).addEventListener("click", () => {
      setGrams("");
      grams.focus();
    });
    qty?.addEventListener("input", () => {
      item.qty = qty.value;
      updateTotals();
    });
    remove.addEventListener("click", () => removeItem(item, node));
    node.addEventListener("focusin", () => {
      if (state.active !== item) setActive(item);
    });

    syncItem(item, node);
    return node;
  }

  function removeItem(item, node) {
    $(".js-remove", node).disabled = true;
    node.classList.add("is-leaving");
    // ждём конец анимации из CSS; без анимации (reduced motion) список пуст и ждать нечего
    Promise.allSettled(node.getAnimations().map((animation) => animation.finished)).then(() => {
      state.items.splice(state.items.indexOf(item), 1);
      renderItems();
    });
  }

  // enterIndex: какой блок только что добавили, чтобы анимировать появление только его
  function renderItems(enterIndex = -1) {
    const container = $("#items");
    const panels = $$(".panel");
    const before = panels.map((panel) => panel.getBoundingClientRect());
    const itemsBefore = new Map(state.items.filter((item) => itemNodes.has(item)).map((item) => [item, itemNodes.get(item).getBoundingClientRect()]));
    panels.forEach((panel) => panel.getAnimations().forEach((animation) => animation.cancel()));
    container.replaceChildren();

    state.items.forEach((item, index) => {
      const node = createItemNode(item);
      if (index === enterIndex) node.classList.add("is-entering");
      container.append(node);
    });

    $(".layout").classList.toggle("is-many", state.items.length > 2); // раскладка планшета, см. calc.css
    updateTotals();
    if (state.items.includes(state.active)) syncBoard();
    else setActive(state.items[0]);
    syncCalcBase(); // итоговые размеры блоков нужны до анимации
    // первый показ при загрузке страницы не анимируем
    if (itemsRendered) {
      animateItems(itemsBefore);
      animateLayout(panels, before);
    }
    itemsRendered = true;
  }

  function itemCost(item) {
    const rate = findRate(item.probeId);
    if (!rate) return 0;
    const count = SHOW_QTY ? Math.floor(parseNumber(item.qty)) : 1;
    const cost = pricePerGram(rate) * parseNumber(item.grams) * count;
    return Math.round(cost * 100) / 100;
  }

  function updateTotals() {
    const subtotals = $$(".js-subtotal");
    let total = 0;

    state.items.forEach((item, index) => {
      const cost = itemCost(item);
      total += cost;
      subtotals[index].value = formatMoney(cost);
    });

    $("#total").value = formatMoney(total);
    $("#result-count").textContent = `Изделий: ${state.items.length}`;
    saveItems();
  }

  // ---------- Загрузка курса ----------

  async function loadRates() {
    const status = $("#board-status");

    try {
      const response = await fetch(API_URL, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      state.rates = data.rates;
      state.currency = data.currency_label || "сом";
      $("#updated").textContent = data.updated_at
        ? "Обновлено " +
          new Date(data.updated_at).toLocaleString("ru-RU", {
            day: "numeric",
            month: "long",
            hour: "2-digit",
            minute: "2-digit",
          })
        : "";

      status.hidden = state.rates.length > 0;
      status.textContent = "Курс пока не установлен. Загляните позже.";
    } catch {
      status.hidden = false;
      status.textContent = "Не удалось загрузить курс. Проверьте интернет и обновите страницу.";
    }

    initBoardMetals();
    renderItems();
  }

  // Высота калькулятора с одним изделием (без растяжения сеткой): по ней итог не бывает короче калькулятора.
  // Считаем из высот содержимого, а не самого блока, чтобы не было обратной связи с min-height итога
  function syncCalcBase() {
    const calc = $(".calc");
    const first = $(".item", calc);
    if (!first) return;

    const style = getComputedStyle(calc);
    const sides = ["paddingTop", "paddingBottom", "borderTopWidth", "borderBottomWidth"];
    const frame = sides.reduce((sum, side) => sum + parseFloat(style[side]), 0);
    const base = frame + $(".panel-head", calc).offsetHeight + parseFloat(style.rowGap) + first.offsetHeight;
    $(".layout").style.setProperty("--calc-base", `${Math.ceil(base)}px`);
  }

  // Пересчёт при любом изменении калькулятора: ширина, перенос чипов, смена металла, добавление изделий
  new ResizeObserver(syncCalcBase).observe($(".calc"));

  $("#add-item").addEventListener("click", () => {
    state.items.unshift(newItem());
    renderItems(0);
    // фокус в поле веса удобен с мышью, а на тачскринах он выдвигает клавиатуру и мешает
    if (window.matchMedia("(hover: hover)").matches) $(".js-grams").focus();
  });

  state.items = loadItems() || [newItem()];
  loadRates();
})();
