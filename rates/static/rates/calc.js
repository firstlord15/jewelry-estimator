"use strict";

(() => {
  const API_URL = "/api/rates/";
  const STORAGE_KEY = "jewelry-calc-items";
  const SHOW_QTY = document.body.dataset.showQty === "1";
  const RESIZE_MS = 200;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let itemsRendered = false;

  const state = {
    rates: [],
    currency: "сом",
    items: [],
  };

  const $ = (selector, root = document) => root.querySelector(selector);
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

  // ---------- Табло курса ----------

  function renderBoard(updatedAt) {
    const board = $("#board");
    board.replaceChildren();

    for (const rate of state.rates) {
      const head = createElement("div", "rate-head");
      head.append(createElement("span", "stamp", rate.fineness), createElement("span", "", rate.metal_label));

      const card = createElement("div", `rate-card glass rate-${rate.metal}`);
      card.append(head, createElement("div", "rate-price", money.format(pricePerGram(rate))), createElement("div", "rate-unit", `${state.currency} за 1 г`));
      board.append(card);
    }

    $("#updated").textContent = updatedAt
      ? "Обновлено " +
        new Date(updatedAt).toLocaleString("ru-RU", {
          day: "numeric",
          month: "long",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";
  }

  // ---------- Блоки изделий ----------

  // Плавно меняем высоту списка (а значит, и панели) со старой на новую
  function animateResize(container, from) {
    const to = container.offsetHeight;
    if (from === to || reduceMotion.matches) return;

    container.style.overflow = "hidden";
    const animation = container.animate([{ height: `${from}px` }, { height: `${to}px` }], { duration: RESIZE_MS, easing: "ease-out" });
    const done = () => (container.style.overflow = "");
    animation.onfinish = done;
    animation.oncancel = done;
  }

  // Блок изделия из шаблона: значения из state и обработчики полей
  function createItemNode(item) {
    const node = $("#item-template").content.firstElementChild.cloneNode(true);
    const select = $(".js-probe", node);
    const grams = $(".js-grams", node);
    const qty = $(".js-qty", node);
    const remove = $(".js-remove", node);

    for (const rate of state.rates) {
      const text = `${rate.metal_label} ${rate.fineness} — ${formatMoney(pricePerGram(rate))}/г`;
      select.add(new Option(text, rate.id));
    }

    // Проба могла быть удалена или скрыта, пока человека не было на сайте
    if (!findRate(item.probeId)) item.probeId = defaultProbeId();

    select.disabled = state.rates.length === 0;
    if (item.probeId !== null) select.value = item.probeId;
    grams.value = item.grams;
    if (qty) qty.value = item.qty;
    remove.disabled = state.items.length === 1;

    select.addEventListener("change", () => {
      item.probeId = Number(select.value);
      updateTotals();
    });
    grams.addEventListener("input", () => {
      item.grams = grams.value;
      updateTotals();
    });
    qty?.addEventListener("input", () => {
      item.qty = qty.value;
      updateTotals();
    });
    remove.addEventListener("click", () => removeItem(item, node));

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
    const from = container.offsetHeight;
    container.getAnimations().forEach((animation) => animation.cancel());
    container.replaceChildren();

    state.items.forEach((item, index) => {
      const node = createItemNode(item);
      if (index === enterIndex) node.classList.add("is-entering");
      container.append(node);
    });

    updateTotals();
    // первый показ при загрузке страницы не анимируем
    if (itemsRendered) animateResize(container, from);
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
    const subtotals = document.querySelectorAll(".js-subtotal");
    let total = 0;

    state.items.forEach((item, index) => {
      const cost = itemCost(item);
      total += cost;
      subtotals[index].value = formatMoney(cost);
    });

    $("#total").value = formatMoney(total);
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
      renderBoard(data.updated_at);

      status.hidden = state.rates.length > 0;
      status.textContent = "Курс пока не установлен. Загляните позже.";
    } catch {
      status.hidden = false;
      status.textContent = "Не удалось загрузить курс. Проверьте интернет и обновите страницу.";
    }

    renderItems();
  }

  $("#add-item").addEventListener("click", () => {
    state.items.push(newItem());
    renderItems(state.items.length - 1);
    const inputs = document.querySelectorAll(".js-grams");
    inputs[inputs.length - 1]?.focus();
  });

  state.items = loadItems() || [newItem()];
  loadRates();
})();
