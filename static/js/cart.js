(function () {
  "use strict";

  const storageKey = "saffron-table-cart";
  const themeStorageKey = "saffron-table-theme";
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const themeColorMeta = document.querySelector('meta[name="theme-color"]');
  const fallbackImageMeta = document.querySelector('meta[name="dish-fallback-image"]');
  const fallbackImage = fallbackImageMeta ? fallbackImageMeta.content : "/static/images/dish-placeholder.svg";
  const catalogNode = document.getElementById("menu-items-data");
  let catalog = [];
  if (catalogNode) {
    try {
      catalog = JSON.parse(catalogNode.textContent);
    } catch (error) {
      catalog = [];
    }
  }

  function readSavedTheme() {
    try {
      const savedTheme = localStorage.getItem(themeStorageKey);
      return savedTheme === "light" || savedTheme === "dark" ? savedTheme : null;
    } catch (error) {
      return null;
    }
  }

  function updateThemeControls(theme) {
    if (themeToggle) {
      const isDark = theme === "dark";
      themeToggle.setAttribute("aria-pressed", String(isDark));
      themeToggle.setAttribute(
        "aria-label",
        `Currently ${theme} theme. Switch to ${isDark ? "light" : "dark"} theme.`
      );
    }
    if (themeColorMeta) {
      themeColorMeta.content = theme === "dark" ? "#171717" : "#fbf5e9";
    }
  }

  function applyTheme(theme, savePreference = false) {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    updateThemeControls(theme);
    if (savePreference) {
      try {
        localStorage.setItem(themeStorageKey, theme);
      } catch (error) {
        // The current page still changes theme if browser storage is unavailable.
      }
    }
  }

  applyTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(nextTheme, true);
    });
  }

  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  const followSystemTheme = (event) => {
    if (!readSavedTheme()) applyTheme(event.matches ? "dark" : "light");
  };
  if (systemTheme.addEventListener) systemTheme.addEventListener("change", followSystemTheme);
  else if (systemTheme.addListener) systemTheme.addListener(followSystemTheme);

  window.addEventListener("storage", (event) => {
    if (event.key !== themeStorageKey) return;
    applyTheme(readSavedTheme() || (systemTheme.matches ? "dark" : "light"));
  });

  document.querySelectorAll("img[data-fallback-image]").forEach((image) => {
    image.addEventListener("error", () => {
      const fallbackImage = image.dataset.fallbackImage;
      if (fallbackImage && image.src !== new URL(fallbackImage, document.baseURI).href) {
        image.src = fallbackImage;
      } else {
        image.classList.add("image-unavailable");
      }
    });
  });

  function readCart() {
    try {
      const parsed = JSON.parse(localStorage.getItem(storageKey) || "{}");
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function writeCart(cart) {
    localStorage.setItem(storageKey, JSON.stringify(cart));
    updateCount(cart);
  }

  function updateCount(cart) {
    const count = Object.values(cart).reduce((sum, quantity) => sum + Number(quantity || 0), 0);
    document.querySelectorAll("[data-cart-count]").forEach((node) => {
      node.textContent = String(count);
      node.setAttribute("aria-label", `${count} items in cart`);
    });
  }

  function formatMoney(amount) {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(amount);
  }

  function renderCart() {
    const cartLines = document.getElementById("cart-items");
    if (!cartLines) return;
    const cart = readCart();
    cartLines.replaceChildren();
    let subtotal = 0;
    let lineCount = 0;
    let cartChanged = false;
    Object.entries(cart).forEach(([id, rawQuantity]) => {
      const item = catalog.find((entry) => String(entry.id) === id);
      const quantity = Math.max(1, Math.min(99, Number.parseInt(rawQuantity, 10) || 1));
      if (!item) {
        delete cart[id];
        cartChanged = true;
        return;
      }
      const price = Number(item.price);
      if (!Number.isFinite(price)) return;
      subtotal += price * quantity;
      lineCount += 1;

      const row = document.createElement("article");
      row.className = "cart-line";
      const photo = document.createElement("img");
      photo.className = "cart-line-photo";
      photo.addEventListener("error", () => {
        if (photo.src !== new URL(fallbackImage, document.baseURI).href) photo.src = fallbackImage;
        else photo.classList.add("image-unavailable");
      });
      photo.src = item.image || fallbackImage;
      photo.alt = "";
      const info = document.createElement("div");
      info.className = "cart-line-info";
      const name = document.createElement("h2");
      name.textContent = item.name;
      const category = document.createElement("span");
      category.textContent = item.category;
      info.append(name, category);
      const controls = document.createElement("div");
      controls.className = "quantity-control";
      const decrease = document.createElement("button");
      decrease.type = "button";
      decrease.textContent = "−";
      decrease.setAttribute("aria-label", `Remove one ${item.name}`);
      decrease.addEventListener("click", () => changeQuantity(id, -1));
      const amount = document.createElement("span");
      amount.textContent = String(quantity);
      const increase = document.createElement("button");
      increase.type = "button";
      increase.textContent = "+";
      increase.setAttribute("aria-label", `Add one ${item.name}`);
      increase.addEventListener("click", () => changeQuantity(id, 1));
      controls.append(decrease, amount, increase);
      const linePrice = document.createElement("strong");
      linePrice.className = "cart-line-price";
      linePrice.textContent = formatMoney(price * quantity);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-line";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        const next = readCart();
        delete next[id];
        writeCart(next);
        renderCart();
      });
      const trailing = document.createElement("div");
      trailing.className = "cart-line-trailing";
      trailing.append(linePrice, remove);
      row.append(photo, info, controls, trailing);
      cartLines.append(row);
    });

    const empty = document.getElementById("cart-empty");
    const summary = document.getElementById("cart-summary");
    if (empty) empty.hidden = lineCount > 0;
    if (summary) summary.hidden = lineCount === 0;
    const tax = Math.round(subtotal * 0.08 * 100) / 100;
    setText("cart-subtotal", formatMoney(subtotal));
    setText("cart-tax", formatMoney(tax));
    setText("cart-total", formatMoney(subtotal + tax));
    if (cartChanged) writeCart(cart);
    updateCount(readCart());
  }

  function changeQuantity(id, change) {
    const cart = readCart();
    const nextQuantity = (Number.parseInt(cart[id], 10) || 0) + change;
    if (nextQuantity < 1) delete cart[id];
    else cart[id] = Math.min(99, nextQuantity);
    writeCart(cart);
    renderCart();
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = value;
  }

  function renderCheckout() {
    const container = document.getElementById("checkout-items");
    if (!container) return;
    const cart = readCart();
    const subtotal = Object.entries(cart).reduce((sum, [id, quantity]) => {
      const item = catalog.find((entry) => String(entry.id) === id);
      return item ? sum + Number(item.price) * Number(quantity || 0) : sum;
    }, 0);
    container.replaceChildren();
    Object.entries(cart).forEach(([id, quantity]) => {
      const item = catalog.find((entry) => String(entry.id) === id);
      if (!item) return;
      const row = document.createElement("div");
      row.className = "checkout-item-row";
      const label = document.createElement("span");
      label.textContent = `${quantity} × ${item.name}`;
      const price = document.createElement("strong");
      price.textContent = formatMoney(Number(item.price) * Number(quantity));
      row.append(label, price);
      container.append(row);
    });
    const tax = Math.round(subtotal * 0.08 * 100) / 100;
    setText("checkout-subtotal", formatMoney(subtotal));
    setText("checkout-tax", formatMoney(tax));
    setText("checkout-total", formatMoney(subtotal + tax));
  }

  const menuSearch = document.getElementById("menu-search");
  if (menuSearch) {
    const menuItems = Array.from(document.querySelectorAll("[data-menu-item]"));
    const noResults = document.getElementById("menu-no-results");
    menuSearch.addEventListener("input", () => {
      const query = menuSearch.value.trim().toLocaleLowerCase("en-IN");
      let visibleCount = 0;
      menuItems.forEach((menuItem) => {
        const searchText = (menuItem.dataset.searchText || "").toLocaleLowerCase("en-IN");
        menuItem.hidden = !searchText.includes(query);
        if (!menuItem.hidden) visibleCount += 1;
      });
      if (noResults) noResults.hidden = visibleCount > 0;
    });
  }

  document.querySelectorAll("[data-add-to-cart]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.itemId;
      const cart = readCart();
      cart[id] = Math.min(99, (Number.parseInt(cart[id], 10) || 0) + 1);
      writeCart(cart);
      const original = button.innerHTML;
      button.innerHTML = '<i class="bi bi-check2"></i><span>Added</span>';
      button.classList.add("is-added");
      window.setTimeout(() => {
        button.innerHTML = original;
        button.classList.remove("is-added");
      }, 850);
    });
  });

  const checkoutForm = document.getElementById("checkout-form");
  if (checkoutForm) {
    checkoutForm.addEventListener("submit", (event) => {
      const cart = readCart();
      if (Object.keys(cart).length === 0) {
        event.preventDefault();
        window.location.href = "/cart/";
        return;
      }
      document.getElementById("cart-json").value = JSON.stringify(cart);
    });
  }

  document.querySelectorAll("[data-copy-order]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copyOrder);
        button.innerHTML = '<i class="bi bi-check2"></i>';
      } catch (error) {
        window.prompt("Copy your order ID:", button.dataset.copyOrder);
      }
    });
  });

  if (document.querySelector("[data-order-complete]")) {
    localStorage.removeItem(storageKey);
  }
  updateCount(readCart());
  renderCart();
  renderCheckout();
})();