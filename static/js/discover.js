// discover.js
// Loads the cards for the themed browse pages (discover.html): Brands, Categories, New Drops and Hot!
// Data comes from /api/storefronts and Anthony Jackson's /api/menu routes.

const page = document.body.dataset.page;
const results = document.getElementById("results");
const searchInput = document.getElementById("browseSearch");

function esc(text) {
  const d = document.createElement("div");
  d.textContent = text == null ? "" : String(text);
  return d.innerHTML;
}

function showMessage(text) {
  results.innerHTML = `<p class="state-message">${esc(text)}</p>`;
}

function getJSON(url) {
  return fetch(url).then(r => {
    if (!r.ok) throw new Error("bad response");
    return r.json();
  });
}

function media(imageUrl, alt, placeholder) {
  if (imageUrl) {
    return `<img class="card-media" src="${esc(imageUrl)}" alt="${esc(alt)}">`;
  }
  return `<div class="card-media"><span class="card-placeholder">${esc(placeholder)}</span></div>`;
}

// ---------- Listing cards (New Drops, Hot!) ----------

function listingCard(item) {
  const saves = page === "hot" && item.wishlist_count
    ? `<p class="card-meta">Saved ${item.wishlist_count} time${item.wishlist_count === 1 ? "" : "s"}</p>`
    : "";
  return `
    <a class="item-card" href="/storefronts/${item.storefront_id}">
      ${media(item.image_url, item.title, item.brand_name)}
      <div class="card-body">
        <div class="card-eyebrow">${esc(item.brand_name)}</div>
        <h3 class="card-title">${esc(item.title)}</h3>
        ${saves}
        <div class="card-footer">
          <span class="card-price">$${Number(item.price).toFixed(2)}</span>
          <span class="card-action">View brand →</span>
        </div>
      </div>
    </a>`;
}

function loadListings(url) {
  getJSON(url)
    .then(items => {
      if (!items.length) return showMessage("Nothing here yet. Check back soon.");
      results.innerHTML = items.map(listingCard).join("");
    })
    .catch(() => showMessage("Could not load listings. Please try again."));
}

// ---------- Storefront cards (Brands, Categories) ----------

function storefrontCard(store) {
  const count = store.item_count != null
    ? `${store.item_count} item${store.item_count === 1 ? "" : "s"}`
    : "";
  return `
    <a class="item-card" href="/storefronts/${store.id}">
      ${media(store.banner_url || store.logo_url, store.brand_name, store.brand_name)}
      <div class="card-body">
        <div class="card-eyebrow">${esc(store.categories || "Student brand")}</div>
        <h3 class="card-title">${esc(store.brand_name)}</h3>
        ${store.bio ? `<p class="card-meta">${esc(store.bio)}</p>` : ""}
        <div class="card-footer">
          <span class="card-meta">${count}</span>
          <span class="card-action">Visit storefront →</span>
        </div>
      </div>
    </a>`;
}

function matchesSearch(store, query) {
  if (!query) return true;
  const text = `${store.brand_name} ${store.categories || ""} ${store.bio || ""}`.toLowerCase();
  return text.includes(query);
}

function storeCategories(store) {
  return String(store.categories || "").split(",").map(c => c.trim()).filter(Boolean);
}

function loadStorefronts() {
  let stores = [];
  let activeCategory = null;
  const filters = document.getElementById("categoryFilters");
  const heading = document.getElementById("resultsHeading");

  function render() {
    const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
    const shown = stores.filter(s =>
      matchesSearch(s, query) &&
      (!activeCategory || storeCategories(s).includes(activeCategory))
    );
    if (heading) heading.textContent = activeCategory ? `${activeCategory} storefronts` : "Storefronts";
    if (!shown.length) return showMessage("No storefronts match that yet.");
    results.innerHTML = shown.map(storefrontCard).join("");
  }

  function renderFilters() {
    const names = [...new Set(stores.flatMap(storeCategories))].sort((a, b) => a.localeCompare(b));
    filters.innerHTML = ["All", ...names].map(name => {
      const pressed = (name === "All" && !activeCategory) || name === activeCategory;
      return `<button type="button" class="category-chip" data-category="${esc(name)}" aria-pressed="${pressed}">${esc(name)}</button>`;
    }).join("");
  }

  if (filters) {
    filters.addEventListener("click", e => {
      const chip = e.target.closest(".category-chip");
      if (!chip) return;
      activeCategory = chip.dataset.category === "All" ? null : chip.dataset.category;
      renderFilters();
      render();
    });
  }
  if (searchInput) searchInput.addEventListener("input", render);

  getJSON("/api/storefronts")
    .then(data => {
      stores = data;
      if (!stores.length) return showMessage("No storefronts are open yet.");
      if (filters) renderFilters();
      render();
    })
    .catch(() => showMessage("Could not load storefronts. Please try again."));
}

if (page === "new") loadListings("/api/menu/new-drops");
else if (page === "hot") loadListings("/api/menu/hot");
else if (page === "brands" || page === "categories") loadStorefronts();
