/* 
storefront.js

  The Vault Campus Marketplace
  CSC 405 Sp 26
  Created by Day Ekoi - Iteration 4
  Date: 3/18/2026 - 3/22/2026
  Updated by Day Ekoi - Iteration 5 - 4/20/26 - fetchStorefronts now maps preview_image_1-4 to card carousel; falls back to banner_url if no previews set
  Updated by Day Ekoi - Iteration 5 - 4/20/26 - removed add-to-cart form from storefront cards (size, qty, add to bag); kept version history via comments

Description: This file is responsible for the behavior of the storefront homepage. As of now, it stores sample storefront data, creates storefront cards using that data, 
inserts the cards into the storefront grid in storefront.html, and handles the image carousel functionality for each storefront cards. 

This file works with:
- storefront.html
- storefront.css

This file will be updated to fetch real storefront data from the Flask API routes and display the actual storefronts created by users in the database.



STOREFRONT DATA

THESE ARE PLACEHOLDERS FOR NOW!!!!
it holds temp storefront data, creation of storefront cards, inserting them into the page, and handling image functionality 

Fields: 
    id: unique identifier for the storefront
    name: name of the storefront
    categories: array of categories/tags associated with the storefront
    items: number of items in the storefront
    logo: URL for the storefront's logo image
    images: array of URLs for the storefront's carousel images (4 images per storefront)


What needs to be replaced later: 
- The storefront data in the storefronts array to be fetched from the Flask API instead of being hardcoded, recieve JSON, render real storefronts
- Functionality & routing: menu button opens navigation pane, cart button routes to cart, account button routes to profile, Enter Storefront opens that store page
- Searching and page: search storefront name, 10 stores per page 
*/


let storefronts = [];




/* STROREFRONT CARDS 

Storefront cards/grid boxes will be generated dynamically from the storefronts array above. 
Each storefront will have a card with its logo, name, categories, item count, and about 4 images to appease to buyers.
 There are left and right arrows to navigate through the images.
*/

// Get the storefront grid container from the HTML where the cards will be inserted
const grid = document.getElementById("storefrontGrid");


// CREATE STOREFRONT CARD

/* 
The purpose of this function is to create a storefront card element from a storefront object.

Input: stores a storefront object from the storefronts array 
Output: Returns a HTML element (card) ready to be inserted into the page
*/
function createCard(store) {
  let index = 0; // keeps track of which image is currently being shown inside the card's image carousel. Starts at 0 (first image)

  const card = document.createElement("div"); // Created new element in memory
  card.className = "storefront-card"; // assigns the storefront-card class to the new element for styling purposes

  const categories = Array.isArray(store.categories) ? store.categories : [];
  const images = Array.isArray(store.images) ? store.images.filter(Boolean) : [];
  const logo = store.logo || null;
  const items = store.items ?? 0;
  const itemLabel = `${items} ${items === 1 ? "Item" : "Items"}`;
  const metaLabel = categories.length > 0
    ? `${itemLabel} | ${categories.join(" • ")}`
    : itemLabel;

  card.innerHTML = `
    <div class="storefront-card-body">
      <div class="storefront-header">
        ${logo
          ? `<img class="storefront-logo" src="${logo}">`
          : `<div class="storefront-logo"></div>`
        }
        <div>
          <h2 class="storefront-name">${store.name}</h2>
          <p class="storefront-meta">
            ${metaLabel}
          </p>
        </div>
      </div>

      <div class="carousel-shell">
        <button class="carousel-btn left">&#10094;</button>
        ${images.length > 0 ? `<img class="carousel-image" src="${images[0]}">` : `<div class="carousel-image"></div>`}
        <button class="carousel-btn right">&#10095;</button>
      </div>

      <!-- Removed by Day Ekoi - Iteration 5 - 4/20/26: add-to-cart form removed from storefront cards.
           Cart/size/qty actions belong on the individual listing page, not the storefront browse view.
      <form action="/auth/add_to_cart" method="POST" class="bag-form">
        <input type="hidden" name="item_id" value="${store.id}">
        <input type="hidden" name="item_name" value="${store.name} Official Item">
        <input type="hidden" name="price" value="45.00">
        <div class="selection-row">
          <select name="size" class="vault-select">
            <option value="S">S</option>
            <option value="M">M</option>
            <option value="L">L</option>
            <option value="XL">XL</option>
          </select>
          <input type="number" name="quantity" value="1" min="1" class="vault-qty">
        </div>
        <button type="submit" class="add-bag-btn">Add to Bag</button>
      </form>
      -->
    </div>

    <div class="storefront-footer">
      <button class="enter-btn">Enter Storefront</button>
    </div>
  `;


// After card generation, references are grabbed to import elements inside the card

  const img = card.querySelector(".carousel-image");
  const left = card.querySelector(".left");
  const right = card.querySelector(".right");
  const enterBtn = card.querySelector(".enter-btn");


// Card Arrow button functionality 

// left arrow functionality: once clicked the index variable is decremented by 1 and moves one image backwards in the array
  left.onclick = () => {
    index = (index - 1 + images.length) % images.length;
    img.src = images[index];
  };

// right arrow functionality: once clicked, indec is incremeted by 1 and moves one image forward in the array 
  right.onclick = () => {
    index = (index + 1) % images.length;
    img.src = images[index];
  };

  // Enter storefront routing
  enterBtn.onclick = () => {
    window.location.href = `/storefronts/${store.id}`;
  };

  // Lightbox: click carousel image to see full preview - Added by Day Ekoi 4/20/26
  if (img && img.tagName === "IMG") {
    img.addEventListener("click", () => {
      const overlay = document.getElementById("lightboxOverlay");
      const lightboxImg = document.getElementById("lightboxImg");
      lightboxImg.src = img.src;
      overlay.classList.add("active");
    });
  }

  return card; // returns the fully built card
}


// Close lightbox when clicking the overlay - Added by Day Ekoi 4/20/26
document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("lightboxOverlay");
  if (overlay) {
    overlay.addEventListener("click", () => {
      overlay.classList.remove("active");
    });
  }
});


/*  function to render all stores

this function loops through all storefrotn objects in the storefronts array, creates a card for each, and then inserts the cards into the storefront grid 
*/
// Updated 10/27/26: renders only the current page of stores that match the search box
// and the selected category chip, plus an empty state when nothing matches
const STORES_PER_PAGE = 6;
const browseState = {
  query: "",      // search box text
  category: "",   // selected chip ("" = All)
  page: 1,
};

function getVisibleStorefronts() {
  const query = browseState.query.toLowerCase();
  const category = browseState.category.toLowerCase();
  return storefronts.filter(store => {
    const matchesQuery = !query || store.name.toLowerCase().includes(query);
    const matchesCategory = !category || store.categories.some(c => c.toLowerCase() === category);
    return matchesQuery && matchesCategory;
  });
}

function renderEmptyState() {
  const filtersOn = browseState.query || browseState.category;
  const box = document.createElement("div");
  box.className = "empty-state";

  const title = document.createElement("h2");
  const text = document.createElement("p");
  const action = document.createElement(filtersOn ? "button" : "a");
  action.className = "empty-state-btn";

  if (filtersOn) {
    // built with textContent so a search can't inject HTML into the page
    title.textContent = "No matches";
    const parts = [];
    if (browseState.query) parts.push(`"${browseState.query}"`);
    if (browseState.category) parts.push(browseState.category);
    text.textContent = `No storefronts match ${parts.join(" in ")} yet.`;
    action.type = "button";
    action.textContent = "Clear filters";
    action.addEventListener("click", clearFilters);
  } else {
    title.textContent = "No storefronts yet";
    text.textContent = "Be the first to open shop on campus.";
    action.href = "/storefronts/create";
    action.textContent = "Create Storefront";
  }

  box.append(title, text, action);
  grid.appendChild(box);
}

function renderPagination(totalPages) {
  const pagination = document.getElementById("pagination");
  if (!pagination) return;
  pagination.hidden = totalPages <= 1;
  document.getElementById("pageIndicator").textContent = `Page ${browseState.page} of ${totalPages}`;
  document.getElementById("prevPageBtn").disabled = browseState.page <= 1;
  document.getElementById("nextPageBtn").disabled = browseState.page >= totalPages;
}

function renderStorefronts() {
  if (!grid) return; // Updated by Day E 3/22/26
  grid.innerHTML = ""; // this clears the gird. Useful for if there needs to be re-rendering 

  const visible = getVisibleStorefronts();
  const totalPages = Math.max(1, Math.ceil(visible.length / STORES_PER_PAGE));
  browseState.page = Math.min(browseState.page, totalPages);

  if (!visible.length) {
    renderEmptyState();
  } else {
    const start = (browseState.page - 1) * STORES_PER_PAGE;
    visible.slice(start, start + STORES_PER_PAGE).forEach(store => { // loops through this page's stores
      const card = createCard(store); //creates a card for the current store object
      grid.appendChild(card); // inserts the created card into the storefront grid in the HTML
    });
  }

  renderPagination(totalPages);
}

function setCategory(category) {
  browseState.category = category;
  browseState.page = 1;
  document.querySelectorAll("#filterChips .chip[data-category]").forEach(chip => {
    const active = chip.dataset.category === category;
    chip.classList.toggle("active", active);
    chip.setAttribute("aria-pressed", String(active));
    // on phones the chips are one sideways-scrolling row, so keep the selected one in view
    if (active) chip.scrollIntoView({ block: "nearest", inline: "nearest" });
  });
  renderStorefronts();
}

function clearFilters() {
  browseState.query = "";
  if (searchInput) searchInput.value = "";
  setCategory("");
}


/* FETCH STOREFRONTS FROM FLASK API

This function requests storefront data from the Flask backend.
If the backend returns storefront data successfully, it replaces the placeholder storefronts array.
If the backend route is not ready yet or fails, the placeholder data will still be used.
*/
async function fetchStorefronts() {
  try {
    const response = await fetch("/api/storefronts");

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();

    const storefrontArray = Array.isArray(data) ? data : [data]; // Updated by Day E 3/22/26

    storefronts = storefrontArray.map(store => { //updated 4/20/2026
      const previewImages = [
        store.preview_image_1,
        store.preview_image_2,
        store.preview_image_3,
        store.preview_image_4,
      ].filter(Boolean);

      return {
        id: store.id,
        name: store.brand_name || "Unnamed Storefront",
        categories: Array.isArray(store.categories)
          ? store.categories
          : String(store.categories || "")
              .split(",")
              .map(category => category.trim())
              .filter(Boolean),
        items: store.item_count || 0,
        logo: store.logo_url || null,
        images: previewImages.length > 0 ? previewImages : (store.banner_url ? [store.banner_url] : [])
      };
    });

    renderStorefronts();
  } catch (error) {
    console.error("Error fetching storefronts from Flask API:", error);
    if (grid) grid.innerHTML = `<p style="color:#888; font-style:italic; text-align:center; grid-column:1/-1; padding:2rem;">Could not load storefronts. Please try again.</p>`;
  }
}

// Navigation pane functionality: moved to cove_header.js on 10/27/26 (shared with the Create pages)

console.log(storefronts); // logs the storefronts array to the console for debugging purposes
console.log(grid); // logs the storefront grid element to the console for debugging purposes

// SEARCH BAR FUNCTIONALITY
// Added by Day E 4/9/26
// filters storefront cards in real time as the user types in the search bar

const searchInput = document.getElementById("searchInput");

// Updated 10/27/26: search now works together with the category chips and pagination
// (see renderStorefronts above) instead of rendering its own list
if (searchInput) {
    searchInput.addEventListener("input", () => {
        browseState.query = searchInput.value.trim();
        browseState.page = 1;
        renderStorefronts();
    });
}

// category chips (Added 10/27/26)
document.querySelectorAll("#filterChips .chip[data-category]").forEach(chip => {
    // clicking the selected category again clears it (there's no "All" link in the category bar)
    chip.addEventListener("click", () => {
        setCategory(browseState.category === chip.dataset.category ? "" : chip.dataset.category);
    });
});

// Previous / Next buttons (Added 10/27/26)
const prevPageBtn = document.getElementById("prevPageBtn");
const nextPageBtn = document.getElementById("nextPageBtn");
if (prevPageBtn && nextPageBtn) {
    prevPageBtn.addEventListener("click", () => {
        browseState.page -= 1;
        renderStorefronts();
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
    nextPageBtn.addEventListener("click", () => {
        browseState.page += 1;
        renderStorefronts();
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
}

// Added 10/27/26: the header on the Create pages links here with ?q=... or ?category=...
const startParams = new URLSearchParams(window.location.search);
if (startParams.get("q") && searchInput) {
    searchInput.value = startParams.get("q");
    browseState.query = searchInput.value.trim();
}
if (startParams.get("category")) {
    setCategory(startParams.get("category"));
}

/* Initial render of the storefront cards. This will display the storefronts on the page when it is first loaded. */
fetchStorefronts(); // Updated by Day E 4/9/26 - this will now fetch real storefront data from the Flask API and then render the storefronts. If the API route is not ready or fails, it will fallback to rendering the placeholder storefronts. */

/* renderStorefronts(); // Updated by Day E 3/22/26 */

// Unread message badge: moved to cove_header.js on 10/27/26 (shared with the Create pages)
