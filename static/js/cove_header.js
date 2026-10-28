/*
    cove_header.js

    The Pirate Cove Campus Marketplace
    CSC 405 Sp 26'
    Created 10/27/26 for the Pirate Cove redesign

Description:
Runs the shared header from templates/partials/cove_header.html:
- opens and closes the side menu
- keeps the unread-messages badge up to date (every 30 seconds while the tab is visible)
- on pages without the storefront grid (Create Storefront, Create Listing), the search box
  and category links open the Storefronts page with that search or category applied.
  On the Storefronts page itself, storefront.js filters the stores in place instead.
*/

(function () {
  const navPane = document.getElementById("navPane");
  const navOverlay = document.getElementById("navOverlay");
  const menuBtn = document.querySelector(".cove-header .menu-btn");

  // ---------- side menu ----------
  function setMenuOpen(open) {
    if (!navPane || !navOverlay) return;
    navPane.classList.toggle("active", open);
    navOverlay.classList.toggle("active", open);
    if (menuBtn) menuBtn.setAttribute("aria-expanded", String(open));
  }

  if (menuBtn) {
    menuBtn.addEventListener("click", () => setMenuOpen(!navPane.classList.contains("active")));
  }
  if (navOverlay) {
    navOverlay.addEventListener("click", () => setMenuOpen(false));
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setMenuOpen(false);
  });

  // ---------- unread messages badge ----------
  async function refreshUnreadBadge() {
    const badge = document.getElementById("unreadBadge");
    if (!badge || document.hidden) return;
    try {
      const response = await fetch("/api/messages/unread-count");
      const data = await response.json();
      const unread = Number(data.unread) || 0;
      badge.textContent = unread > 99 ? "99+" : String(unread);
      badge.hidden = unread === 0;
    } catch (error) {
      console.error("Could not load unread message count:", error);
    }
  }

  refreshUnreadBadge();
  setInterval(refreshUnreadBadge, 30000);

  // ---------- search and categories on pages other than Storefronts ----------
  const onStorefrontsPage = Boolean(document.getElementById("storefrontGrid"));
  if (onStorefrontsPage) return;

  function openStorefronts(params) {
    const query = new URLSearchParams(params).toString();
    window.location.href = "/storefronts" + (query ? `?${query}` : "");
  }

  const searchInput = document.getElementById("searchInput");
  if (searchInput) {
    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        const q = searchInput.value.trim();
        openStorefronts(q ? { q } : {});
      }
    });
  }

  document.querySelectorAll("#filterChips .chip[data-category]").forEach((chip) => {
    chip.addEventListener("click", () => openStorefronts({ category: chip.dataset.category }));
  });
})();
