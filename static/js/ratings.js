/*
    ratings.js
    Made by Anthony Jackson 10/21/26

    Handles the 1 to 5 star storefront ratings on two pages:
    1. The storefront page (/storefronts/<id>): shows the overall rating and lets a
       logged in user click a star to rate the store. They can rate as many times as they want.
    2. The main storefront page (/storefront): adds the overall rating to each storefront card.

    It adds its own styles, so it works without any changes to the CSS files.
    It talks to the routes in controllers/rating_controller.py.
*/

(function () {
  const STYLE = `
    .vault-rating-card { margin: 18px auto; max-width: 900px; padding: 16px 20px; border: 1px solid rgba(255,255,255,0.7);
      border-radius: 16px; background: rgba(8,12,60,0.45); color: #fff; font-family: inherit; }
    .vault-rating-card h3 { margin: 0 0 6px; letter-spacing: 1px; }
    .vault-rating-summary { margin: 0 0 10px; font-size: 1.05rem; }
    .vault-rating-badge, .vault-card-badge { display: inline-block; padding: 2px 10px; border-radius: 999px; background: #fff; color: #1a146a; font-weight: 700; font-size: 0.85rem; margin-left: 6px; }
    .vault-stars { display: flex; gap: 4px; }
    .vault-star { background: none; border: none; cursor: pointer; font-size: 2rem; line-height: 1; color: rgba(255,255,255,0.5); padding: 0 2px; }
    .vault-star.on { color: #ffd54a; }
    .vault-rating-msg { min-height: 1.3em; margin: 8px 0 0; font-size: 0.95rem; }
    .vault-rating-msg.error { color: #ffd1d1; }
    .vault-card-rating { margin-top: 8px; font-size: 0.95rem; }
    .vault-card-rating .vault-stars-static { color: #ffd54a; letter-spacing: 2px; }
  `;

  function addStyles() {
    const style = document.createElement("style");
    style.textContent = STYLE;
    document.head.appendChild(style);
  }

  function starString(avg) {
    const full = Math.round(avg);
    return "\u2605".repeat(full) + "\u2606".repeat(5 - full);
  }

  // ---------- Storefront page ----------
  function setupStorefrontPage(storefrontId) {
    const box = document.getElementById("ratingSection");
    if (!box) return;

    box.className = "vault-rating-card";
    box.innerHTML = `
      <h3>Rate this store</h3>
      <p class="vault-rating-summary" id="ratingSummary">Loading rating...</p>
      <div class="vault-stars" id="ratingStars"></div>
      <p class="vault-rating-msg" id="ratingMsg"></p>
    `;

    const summaryEl = document.getElementById("ratingSummary");
    const starsEl = document.getElementById("ratingStars");
    const msgEl = document.getElementById("ratingMsg");
    const buttons = [];

    function paintStars(count) {
      buttons.forEach((b, i) => b.classList.toggle("on", i < count));
    }

    function showSummary(s) {
      if (s.count === 0) {
        summaryEl.textContent = "No ratings yet. Be the first to rate this store.";
      } else {
        summaryEl.innerHTML = `<span class="vault-stars-static" style="color:#ffd54a">${starString(s.average)}</span> ${s.text}<span class="vault-rating-badge">${s.label}</span>`;
      }
    }

    function setMessage(text, isError) {
      msgEl.textContent = text;
      msgEl.classList.toggle("error", !!isError);
    }

    for (let i = 1; i <= 5; i++) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "vault-star";
      b.textContent = "\u2605";
      b.setAttribute("aria-label", `${i} star${i === 1 ? "" : "s"}`);
      b.addEventListener("mouseenter", () => paintStars(i));
      b.addEventListener("focus", () => paintStars(i));
      b.addEventListener("click", () => submit(i));
      starsEl.appendChild(b);
      buttons.push(b);
    }
    starsEl.addEventListener("mouseleave", () => paintStars(0));

    async function submit(stars) {
      setMessage("Saving...", false);
      try {
        const res = await fetch(`/api/storefronts/${storefrontId}/ratings`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ stars }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
          showSummary(data);
          setMessage(`Thanks! You gave this store ${stars} star${stars === 1 ? "" : "s"}.`, false);
        } else if (res.status === 401) {
          setMessage("Log in to rate this store.", true);
        } else {
          setMessage(data.error || "We couldn't save your rating. Try again.", true);
        }
      } catch (err) {
        setMessage("We couldn't save your rating. Check your connection and try again.", true);
      }
    }

    fetch(`/api/storefronts/${storefrontId}/ratings`)
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(showSummary)
      .catch(() => { summaryEl.textContent = "Couldn't load the rating right now."; });
  }

  // ---------- Main storefront page ----------
  function setupCardRatings() {
    const grid = document.getElementById("storefrontGrid") || document.querySelector(".storefront-grid");
    if (!grid) return;

    let summaries = {};
    let loaded = false;

    function decorate() {
      grid.querySelectorAll(".storefront-card").forEach(card => {
        if (card.querySelector(".vault-card-rating")) return;
        const id = card.dataset.storefrontId;
        if (!id) return;
        const s = summaries[id];
        const body = card.querySelector(".storefront-card-body") || card;
        const line = document.createElement("div");
        line.className = "vault-card-rating";
        if (s && s.count > 0) {
          line.innerHTML = `<span class="vault-stars-static">${starString(s.average)}</span> ${s.text}<span class="vault-card-badge">${s.label}</span>`;
        } else {
          line.textContent = "No ratings yet";
        }
        body.appendChild(line);
      });
    }

    fetch("/api/ratings/summary")
      .then(r => (r.ok ? r.json() : {}))
      .catch(() => ({}))
      .then(data => { summaries = data || {}; loaded = true; decorate(); });

    // Cards are built by storefront.js (and rebuilt on search/paging), so watch for new ones
    new MutationObserver(() => { if (loaded) decorate(); }).observe(grid, { childList: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    addStyles();
    const match = window.location.pathname.match(/^\/storefronts\/(\d+)\/?$/);
    if (match) setupStorefrontPage(match[1]);
    else setupCardRatings();
  });
})();
