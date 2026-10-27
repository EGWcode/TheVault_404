/* The Vault browse page functionality - Noah Green 10/17/2026 */
'use strict';
const PAGE = document.body.dataset.page;
const results = document.getElementById('results');
const search = document.getElementById('browseSearch');
const filters = document.getElementById('categoryFilters');
const heading = document.getElementById('resultsHeading');
const categoryParam = new URLSearchParams(window.location.search).get('category');
let storefronts = [];
let selectedCategory = categoryParam || '';

function element(tag, className = '', text = '') {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text) el.textContent = text;
  return el;
}
function showState(message, type = 'info') {
  const state = element('div', `state-message state-${type}`);

  if (type === 'loading') {
    const spinner = element('div', 'loading-spinner');
    state.appendChild(spinner);
  }

  state.appendChild(element('p', '', message));
  results.replaceChildren(state);
}
function safeImage(url, alt) {
  if (typeof url === 'string' && /^(https?:\/\/|\/static\/|\/uploads\/)/i.test(url)) {
    const img = element('img', 'card-media');
    img.src = url;
    img.alt = alt;
    img.loading = 'lazy';
    img.addEventListener('error', () => img.replaceWith(element('div', 'card-media card-placeholder', 'THE VAULT')), {once:true});
    return img;
  }
  return element('div', 'card-media card-placeholder', 'THE VAULT');
}
function parseCategories(raw) {
  if (Array.isArray(raw)) return raw.map(x => String(x).trim()).filter(Boolean);
  if (typeof raw !== 'string') return [];
  let value = raw;
  if (raw.trim().startsWith('[')) {
    try { const json = JSON.parse(raw); if (Array.isArray(json)) return parseCategories(json); } catch (_err) { /* comma-delimited fallback */ }
  }
  return value.split(',').map(x => x.trim()).filter(Boolean);
}
function buildCard({url, image, title, alt, eyebrow, meta, price, footerText}) {
  const card = element('a', 'item-card');
  card.href = url;
  card.appendChild(safeImage(image, alt || title));
  const body = element('div', 'card-body');
  body.appendChild(element('span', 'card-eyebrow', eyebrow));
  body.appendChild(element('h2', 'card-title', title));
  body.appendChild(element('p', 'card-meta', meta));
  const footer = element('div', 'card-footer');
  if (price !== undefined) footer.appendChild(element('strong', 'card-price', '$' + Number(price).toFixed(2)));
  footer.appendChild(element('span', 'card-action', footerText || 'View Storefront →'));
  body.appendChild(footer);
  card.appendChild(body);
  return card;
}
function storeCard(store) {
  const cats = store.categoryList || [];
  const n = Number(store.item_count) || 0;
  return buildCard({
    url: '/storefronts/' + encodeURIComponent(store.id),
    image: store.preview_image_1 || store.banner_url || store.logo_url,
    title: store.brand_name || 'Unnamed Storefront',
    eyebrow:'Brand',
    meta: `${n} ${n === 1 ? 'listing' : 'listings'}${cats.length ? ' · ' + cats.join(' · ') : ''}`
  });
}
function productCard(item) {
  const meta = PAGE === 'hot'
    ? `${item.brand_name} · ${item.units_ordered} ${item.units_ordered === 1 ? 'unit ordered' : 'units ordered'}`
    : `${item.brand_name} · ${item.status === 'SOLD_OUT' ? 'Sold out' : 'Available'}`;
  return buildCard({
    url: '/storefronts/' + encodeURIComponent(item.storefront_id),
    image:item.image_url,
    title:item.title || 'Untitled Item',
    eyebrow:item.brand_name || 'Storefront',
    meta, price:item.price, footerText:'View in Store →'
  });
}
function drawStores() {
  const term = (search?.value || '').trim().toLocaleLowerCase();
  const matched = storefronts.filter(s => {
    if (selectedCategory && !s.categoryList.some(c => c.toLocaleLowerCase() === selectedCategory.toLocaleLowerCase())) return false;
    if (!term) return true;
    return s.brand_name.toLocaleLowerCase().includes(term) || s.categoryList.some(c => c.toLocaleLowerCase().includes(term));
  });
  matched.sort((a, b) => a.brand_name.localeCompare(b.brand_name));
  results.replaceChildren(...matched.map(storeCard));
  if (!matched.length) {
  showState(
    'No storefronts found. Try another category or search term.',
    'empty'
  );
}
  if (heading) heading.textContent = selectedCategory ? selectedCategory + ' Storefronts' : 'All Storefronts';
}
function drawCategories() {
  const counts = new Map();
  storefronts.forEach(s => s.categoryList.forEach(c => {
    const key = c.toLocaleLowerCase();
    if (!counts.has(key)) counts.set(key, {name:c, count:0});
    counts.get(key).count++;
  }));
  filters.replaceChildren();
  const all = [{name:'All', count:storefronts.length}, ...[...counts.values()].sort((a,b)=>a.name.localeCompare(b.name))];
  all.forEach(c => {
    const button = element('button', 'category-chip', c.name + ' (' + c.count + ')');
    button.type = 'button';
    button.setAttribute('aria-pressed', String(c.name === 'All' ? !selectedCategory : c.name.toLocaleLowerCase() === selectedCategory.toLocaleLowerCase()));
    button.addEventListener('click', () => {
      selectedCategory = c.name === 'All' ? '' : c.name;
      const u = new URL(window.location.href);
      if (selectedCategory) u.searchParams.set('category', selectedCategory);
      else u.searchParams.delete('category');
      history.replaceState(null, '', u);
      drawCategories();
      drawStores();
    });
    filters.appendChild(button);
  });
  if (all.length === 1) {
    filters.appendChild(element('p','card-meta','There are no categories yet. Sellers can assign them while creating storefronts.'));
  }
}
async function loadStores() {
  showState('Loading storefronts...', 'loading');

  try {
    const response = await fetch('/api/storefronts');

    if (!response.ok) {
      throw new Error('HTTP ' + response.status);
    }

    const data = await response.json();

    if (!Array.isArray(data)) {
      throw new Error('Unexpected storefront data');
    }

    storefronts = data
      .filter(s => s && s.id && s.is_active !== false)
      .map(s => ({
        ...s,
        brand_name: String(s.brand_name || 'Unnamed Storefront'),
        categoryList: parseCategories(s.categories)
      }));

    if (!storefronts.length) {
      showState(
        'No storefronts are available right now. Check back soon.',
        'empty'
      );
      return;
    }

    if (PAGE === 'categories') {
      drawCategories();
    }

    drawStores();

  } catch (error) {
    console.error('Storefront browse failed:', error);

    showState(
      'Unable to load storefronts. Please try again.',
      'error'
    );
  }
}
async function loadProducts() {
  showState('Loading listings...', 'loading');

  try {
    const response = await fetch(
      '/api/discover/listings?sort=' + PAGE + '&limit=48'
    );

    if (!response.ok) {
      throw new Error('HTTP ' + response.status);
    }

    const products = await response.json();

    if (!Array.isArray(products)) {
      throw new Error('Unexpected listing data');
    }

    if (!products.length) {
      if (PAGE === 'hot') {
        showState(
          'No popular listings yet. Products will appear here after orders are placed.',
          'empty'
        );
      } else {
        showState(
          'No new drops yet. Check back soon!',
          'empty'
        );
      }

      return;
    }

    results.replaceChildren(...products.map(productCard));

  } catch (error) {
    console.error('Product browse failed:', error);

    showState(
      'Unable to load listings. Please try again.',
      'error'
    );
  }
}
if (search) search.addEventListener('input', drawStores);
if (PAGE === 'brands' || PAGE === 'categories') loadStores();
else if (PAGE === 'new' || PAGE === 'hot') loadProducts();
if (typeof module !== 'undefined') {
  module.exports = {
    showState,
    loadProducts
  };
}