"use strict";

(() => {
  const API_URL = "/api/rates/";
  const STORAGE_KEY = "jewelry-calc-item";
  const SHOW_QTY = document.body.dataset.showQty === "1";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let rendered = false;

  const state = {
    rates: [],
    quickWeights: [], // быстрые веса из админки, числами
    currency: "сом",
    item: { probeId: null, grams: "", qty: "1" },
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

  // ---------- Сохранение изделия в браузере ----------

  function loadItem() {
    try {
      const data = JSON.parse(localStorage.getItem(STORAGE_KEY));
      return data && typeof data === "object" ? data : null;
    } catch {
      return null;
    }
  }

  function saveItem() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.item));
    } catch {
      // приватный режим или запрет cookie: просто не сохраняем
    }
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
        button.addEventListener("click", () =>
          animateChange(() => {
            state.boardMetal = metal;
            syncBoard();
          }),
        );
        return button;
      }),
    );
  }

  // Строки выбранного металла; проба изделия подсвечена
  function syncBoard() {
    state.boardMetal ??= metalOf(state.item.probeId) ?? state.rates[0]?.metal ?? null;

    for (const button of $$("#board-metals .segment")) {
      setPressed(button, button.dataset.metal === state.boardMetal);
    }

    const rows = state.rates
      .filter((rate) => rate.metal === state.boardMetal)
      .map((rate) => {
        const row = createElement("div", "rate-row");
        row.dataset.metal = rate.metal;
        row.classList.toggle("is-active", rate.id === state.item.probeId);
        row.append(createElement("span", "", rate.fineness), createElement("span", "", `${money.format(pricePerGram(rate))} ${state.currency}`));
        return row;
      });
    $("#board").replaceChildren(...rows);
  }

  // ---------- Анимация смены размеров и мест ----------
  //
  // Калькулятор и курс меняют размер скачком, когда меняется металл (меняется число проб).
  // animateChange запоминает вид «до», выполняет изменение и плавно ведёт каждый блок в вид «после».

  let layoutAnimations = [];
  let inChange = false;
  const rectOf = (node) => node.getBoundingClientRect();

  function animateChange(change) {
    if (inChange || !rendered || reduceMotion.matches) {
      change();
      return;
    }

    const panels = $$(".panel");
    const panelsBefore = panels.map(rectOf);
    // прерванную анимацию снимаем уже после замера: он учитывает то, что человек видит сейчас
    panels.forEach((panel) => panel.getAnimations().forEach((animation) => animation.cancel()));

    // Сетка могла остаться замороженной от прерванной анимации: размораживаем до изменения,
    // иначе итоговые размеры строк мы бы считали по старым замороженным
    Object.assign($(".layout").style, { gridTemplateColumns: "", gridTemplateRows: "" });

    inChange = true;
    try {
      change();
    } finally {
      inChange = false;
    }

    // все замеры «после» делаем до старта первой анимации: она сама меняет размеры
    const layout = $(".layout");
    const { gridTemplateColumns, gridTemplateRows } = getComputedStyle(layout);
    const panelsAfter = panels.map(rectOf);

    const animations = animatePanels(panels, panelsBefore, panelsAfter);
    if (!animations.length) return;

    // Строки и колонки сетки замораживаем в итоговых размерах на время анимации: иначе анимируемая
    // высота одного блока пересчитывала бы строки и сдвигала соседей
    Object.assign(layout.style, { gridTemplateColumns, gridTemplateRows });
    layoutAnimations = animations;
    Promise.allSettled(animations.map((animation) => animation.finished)).then(() => {
      // если анимацию прервала новая, сетку разморозит уже она
      if (layoutAnimations === animations) Object.assign(layout.style, { gridTemplateColumns: "", gridTemplateRows: "" });
    });
  }

  // Рамки блоков. На время анимации содержимое обрезается и прижимается к верху, чтобы шапка
  // («Рассчитайте стоимость») не уезжала вместе с центрированием, пока высота рамки меняется
  function animatePanels(panels, before, after) {
    return panels.flatMap((panel, index) => {
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

      Object.assign(panel.style, { overflow: "hidden", justifyContent: "flex-start" });
      const animation = panel.animate(keyframes, { duration: twoSteps ? 320 : 200, easing: twoSteps ? "linear" : "ease-out" });
      animation.onfinish = animation.oncancel = () => Object.assign(panel.style, { overflow: "", justifyContent: "" });
      return [animation];
    });
  }

  // Показывает в блоке изделия текущее состояние: металл, пробу, вес, кнопку очистки
  function syncItem() {
    const item = state.item;
    const node = $("#item");
    const metal = metalOf(item.probeId);
    if (metal) node.dataset.metal = metal;

    for (const segment of $$(".segment", node)) setPressed(segment, segment.dataset.metal === metal);
    for (const chip of $$("#probes .chip", node)) {
      chip.hidden = chip.dataset.metal !== metal;
      setPressed(chip, Number(chip.dataset.id) === item.probeId);
    }
    for (const chip of $$("[data-grams]", node)) setPressed(chip, parseNumber(item.grams) === Number(chip.dataset.grams));
    $("#clear-grams").hidden = item.grams === "";
  }

  // Кнопки металлов, проб и быстрых весов, значения полей и обработчики
  function renderItem() {
    const item = state.item;
    const grams = $("#grams");
    const qty = $("#qty");

    // Проба могла быть удалена или скрыта, пока человека не было на сайте
    if (!findRate(item.probeId)) item.probeId = defaultProbeId();

    const update = () => {
      syncItem();
      updateTotals();
    };
    const showOnBoard = () =>
      animateChange(() => {
        state.boardMetal = metalOf(item.probeId) ?? state.boardMetal;
        syncBoard();
      });
    const chooseProbe = (id) => {
      item.probeId = id;
      update();
      showOnBoard();
    };
    const setGrams = (value) => {
      item.grams = value;
      grams.value = value;
      update();
    };

    $("#metals").append(
      ...metals().map(([metal, label]) => {
        const segment = createButton("segment", label, { metal });
        segment.addEventListener("click", () =>
          animateChange(() => {
            if (metalOf(item.probeId) === metal) return showOnBoard();
            chooseProbe(state.rates.find((rate) => rate.metal === metal).id);
          }),
        );
        return segment;
      }),
    );

    $("#probes").append(
      ...state.rates.map((rate) => {
        const chip = createButton("chip", rate.fineness, { id: rate.id, metal: rate.metal });
        chip.addEventListener("click", () => chooseProbe(rate.id));
        return chip;
      }),
    );

    const quick = $("#quick");
    quick.hidden = state.quickWeights.length === 0;
    quick.append(
      ...state.quickWeights.map((value) => {
        const chip = createButton("chip", `${money.format(value)} г`, { grams: value });
        chip.addEventListener("click", () => setGrams(String(value).replace(".", ",")));
        return chip;
      }),
    );

    grams.value = item.grams;
    if (qty) qty.value = item.qty;

    grams.addEventListener("input", () => setGrams(grams.value));
    $("#clear-grams").addEventListener("click", () => {
      setGrams("");
      grams.focus();
    });
    qty?.addEventListener("input", () => {
      item.qty = qty.value;
      updateTotals();
    });

    animateChange(() => {
      syncItem();
      updateTotals();
      state.boardMetal = metalOf(item.probeId) ?? state.boardMetal;
      syncBoard();
    });
    rendered = true; // первый показ при загрузке страницы не анимируем
  }

  function itemCost(item) {
    const rate = findRate(item.probeId);
    if (!rate) return 0;
    const count = SHOW_QTY ? Math.floor(parseNumber(item.qty)) : 1;
    const cost = pricePerGram(rate) * parseNumber(item.grams) * count;
    return Math.round(cost * 100) / 100;
  }

  function updateTotals() {
    $("#total").value = formatMoney(itemCost(state.item));
    saveItem();
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
      state.quickWeights = (data.quick_weights ?? []).map(Number);
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
    renderItem();
  }

  Object.assign(state.item, loadItem());
  loadRates();
})();
