"use strict";

(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  const header = $(".site-header");
  const mobile = window.matchMedia("(max-width: 960px)");

  // ---------- Выпадающие списки и бургер ----------
  // Кнопка [data-toggle="id"] открывает и закрывает элемент с этим id (класс .is-open).

  const toggles = $$("[data-toggle]");
  const panelOf = (button) => document.getElementById(button.dataset.toggle);

  function setOpen(button, open) {
    button.setAttribute("aria-expanded", String(open));
    panelOf(button)?.classList.toggle("is-open", open);
  }

  function closeAll(except = null) {
    for (const button of toggles) if (button !== except) setOpen(button, false);
  }

  for (const button of toggles) {
    button.addEventListener("click", () => {
      const open = button.getAttribute("aria-expanded") !== "true";
      closeAll(button);
      setOpen(button, open);
    });
  }

  // клик мимо, Esc и выбор ссылки в панели закрывают открытое
  document.addEventListener("click", (event) => {
    const inside = event.target.closest("[data-toggle], .dropdown-menu, .header-panel");
    if (!inside) closeAll();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const opened = toggles.find((button) => button.getAttribute("aria-expanded") === "true");
    closeAll();
    opened?.focus();
  });

  // при переходе на широкий экран мобильная панель сама закрывается
  mobile.addEventListener("change", () => closeAll());

  // ---------- Окно поиска ----------

  const dialog = $("#search-dialog");

  if (dialog) {
    for (const button of $$("[data-open-search]")) {
      button.addEventListener("click", () => {
        closeAll();
        dialog.showModal();
        $("input", dialog)?.focus();
      });
    }
    for (const button of $$("[data-close-search]")) button.addEventListener("click", () => dialog.close());
    // клик по затемнению (по самому <dialog>, а не по содержимому) закрывает окно
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  }

  // ---------- Шапка прячется при прокрутке вниз (на телефоне) ----------

  let lastY = window.scrollY;

  window.addEventListener(
    "scroll",
    () => {
      const y = window.scrollY;
      const menuOpen = $(".is-open", header);
      header.classList.toggle("is-hidden", mobile.matches && !menuOpen && y > lastY && y > 80);
      lastY = y;
    },
    { passive: true },
  );

  // ---------- Счётчики на иконках ----------
  // window.setBadge("cart", 3): обновит все значки этого вида (в шапке и в мобильном меню).

  window.setBadge = (kind, count) => {
    for (const badge of $$(`[data-badge="${kind}"]`)) {
      const changed = Number(badge.dataset.count) !== count;
      badge.dataset.count = count;
      badge.textContent = count > 99 ? "99+" : count;
      if (changed) {
        badge.classList.remove("bump");
        void badge.offsetWidth; // перезапуск анимации
        badge.classList.add("bump");
      }
    }
  };
})();
