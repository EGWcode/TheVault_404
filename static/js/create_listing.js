/*
create_listing.js

The Pirate Cove Campus Marketplace
CSC 405 Sp 26
Created by Elali McNair - Iteration 4
Updated by Day Ekoi - Iteration 5 4/9/26
Updated by Day Ekoi - Iteration 5 4/22/26 - One Size mode, per-size quantities, Made-to-Order
Updated by Nicco Hill 11/12/2026 - inline field errors, limits that match the server, double-submit guard

Purpose:
Handles form submission for Create Listing page. Supports:
- One Size mode (single quantity, no other sizes selectable)
- Multi-size mode (per-size quantity inputs)
- Made-to-Order flag (bypasses inventory limits)
*/

document.addEventListener('DOMContentLoaded', function() {

  function ensureToastRoot() {
    let root = document.getElementById("toastRoot");
    if (!root) {
      root = document.createElement("div");
      root.id = "toastRoot";
      root.className = "toast-root";
      document.body.appendChild(root);
    }
    return root;
  }

  function showListingToast(message, tone = "success") {
    const root = ensureToastRoot();
    const toast = document.createElement("div");
    toast.className = `toast ${tone === "success" ? "success" : "error"}`;
    toast.textContent = message;
    root.appendChild(toast);

    window.setTimeout(() => {
      toast.classList.add("fade-out");
      window.setTimeout(() => toast.remove(), 220);
    }, 2200);
  }

  const listingForm = document.getElementById("listingForm");
  const cancelBtn = document.getElementById("cancelBtn");
  const storefrontSelect = document.getElementById("storefrontSelect");
  const previewInputs = [1, 2, 3, 4].map((index) => document.getElementById(`previewImage${index}`));
  const selectedListingImages = [null, null, null, null];

  // ── Size mode elements ──────────────────────────────────────
  const oneSizeToggle = document.getElementById("oneSizeToggle");
  const multiSizeGrid = document.getElementById("multiSizeGrid");
  const oneSizeQtyRow = document.getElementById("oneSizeQtyRow");
  const oneSizeQty = document.getElementById("oneSizeQty");
  const madeToOrderToggle = document.getElementById("madeToOrderToggle");

  function applyOneSizeMode(enabled) {
    if (!multiSizeGrid || !oneSizeQtyRow) return;
    if (enabled) {
      // Hide multi-size grid, clear all checkboxes and qty inputs
      multiSizeGrid.style.display = "none";
      multiSizeGrid.querySelectorAll('input[name="sizes"]').forEach(cb => {
        cb.checked = false;
      });
      multiSizeGrid.querySelectorAll(".size-qty-input").forEach(inp => {
        inp.value = "";
        inp.style.display = "none";
      });
      oneSizeQtyRow.style.display = "block";
    } else {
      multiSizeGrid.style.display = "";
      oneSizeQtyRow.style.display = "none";
      if (oneSizeQty) oneSizeQty.value = "";
    }
  }

  if (oneSizeToggle) {
    oneSizeToggle.addEventListener("change", () => {
      applyOneSizeMode(oneSizeToggle.checked);
    });
  }

  // Show/hide per-size quantity input when a size checkbox is toggled
  if (multiSizeGrid) {
    multiSizeGrid.querySelectorAll('input[name="sizes"]').forEach(cb => {
      cb.addEventListener("change", () => {
        const row = cb.closest(".size-qty-row");
        if (!row) return;
        const qtyInput = row.querySelector(".size-qty-input");
        if (qtyInput) {
          qtyInput.style.display = cb.checked ? "inline-block" : "none";
          if (!cb.checked) qtyInput.value = "";
        }
      });
    });
  }

  // ── Image preview / drop zone ────────────────────────────────

  function renderSinglePreview(previewContainer, file, zone, slotIndex) {
    if (!previewContainer) return;

    previewContainer.innerHTML = "";
    if (!file) {
      if (zone) {
        zone.classList.remove("has-image");
        zone.style.backgroundImage = "";
        const existingBadge = zone.querySelector(".image-selected-badge");
        if (existingBadge) existingBadge.remove();
      }
      return;
    }

    const thumbWrap = document.createElement("div");
    thumbWrap.className = "thumb-wrap";

    const image = document.createElement("img");
    image.src = URL.createObjectURL(file);
    image.alt = file.name;
    image.onload = () => URL.revokeObjectURL(image.src);

    const fileName = document.createElement("p");
    fileName.className = "thumb-name";
    fileName.textContent = file.name;

    thumbWrap.appendChild(image);
    thumbWrap.appendChild(fileName);
    previewContainer.appendChild(thumbWrap);

    if (zone) {
      const zoneImageUrl = URL.createObjectURL(file);
      zone.style.backgroundImage = `url('${zoneImageUrl}')`;
      zone.classList.add("has-image");

      const existingBadge = zone.querySelector(".image-selected-badge");
      if (existingBadge) existingBadge.remove();

      const badge = document.createElement("span");
      badge.className = "image-selected-badge";
      badge.textContent = `Image ${slotIndex + 1} selected`;
      zone.appendChild(badge);
    }
  }

  function wireDropZone(zone, input, previewContainer, slotIndex) {
    if (!zone || !input) return;

    zone.addEventListener("click", () => input.click());

    zone.addEventListener("dragover", (event) => {
      event.preventDefault();
      zone.classList.add("dragover");
    });

    zone.addEventListener("dragleave", () => {
      zone.classList.remove("dragover");
    });

    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      zone.classList.remove("dragover");

      const droppedFile = event.dataTransfer?.files?.[0];
      const dropError = validateImageFile(droppedFile);
      if (dropError) {
        showListingToast(dropError, "error");
        return;
      }
      if (droppedFile) {
        selectedListingImages[slotIndex] = droppedFile;
        renderSinglePreview(previewContainer, droppedFile, zone, slotIndex);
      }
    });

    input.addEventListener("change", () => {
      const chosenFile = input.files?.[0];
      const chooseError = validateImageFile(chosenFile);
      if (chooseError) {
        showListingToast(chooseError, "error");
        input.value = "";
      }
      selectedListingImages[slotIndex] = chosenFile && !chooseError ? chosenFile : null;
      renderSinglePreview(previewContainer, selectedListingImages[slotIndex], zone, slotIndex);
    });
  }

  [1, 2, 3, 4].forEach((index, arrayIndex) => {
    const zone = document.getElementById(`previewZone${index}`);
    const input = previewInputs[arrayIndex];
    const preview = document.getElementById(`previewPreview${index}`);
    wireDropZone(zone, input, preview, arrayIndex);
  });

  if (storefrontSelect) {
    loadUserStorefronts();
  }

  // ── Validation helpers (Nicco Hill 11/12/2026) ───────────────
  // Errors show next to the field that caused them instead of in alert() popups.
  // Limits match the server (listing_controller.py) and the database columns.

  const MAX_TITLE_LENGTH = 120;          // listings.title VARCHAR(120)
  const MAX_PRICE = 99999999.99;         // listings.price NUMERIC(10,2)
  const MAX_QTY = 100000;
  const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
  const ALLOWED_IMAGE_EXT = /\.(png|jpe?g|gif|webp)$/i;
  const errorSummary = document.getElementById("formErrorSummary");
  const submitBtn = listingForm ? listingForm.querySelector("button[type='submit']") : null;
  let isSubmitting = false;

  function clearErrors() {
    document.querySelectorAll(".field-error").forEach((el) => el.remove());
    document.querySelectorAll("[aria-invalid='true']").forEach((el) => el.removeAttribute("aria-invalid"));
    if (errorSummary) {
      errorSummary.textContent = "";
      errorSummary.classList.remove("visible");
    }
  }

  // Shows `message` under `anchor`. If `field` is given it's highlighted too.
  function showFieldError(anchor, message, field = anchor) {
    if (!anchor) return;
    const error = document.createElement("span");
    error.className = "field-error";
    error.textContent = message;
    const errorId = `err-${Math.random().toString(36).slice(2, 9)}`;
    error.id = errorId;
    anchor.insertAdjacentElement("afterend", error);
    if (field) {
      field.setAttribute("aria-invalid", "true");
      field.setAttribute("aria-describedby", errorId);
    }
  }

  function showSummary(message) {
    if (!errorSummary) return;
    errorSummary.textContent = message;
    errorSummary.classList.add("visible");
  }

  // Number inputs: "", "abc", "2.5" and "-1" are all invalid quantities
  function parseWholeNumber(raw) {
    const text = String(raw ?? "").trim();
    if (!/^\d+$/.test(text)) return NaN;
    return Number(text);
  }

  function validateImageFile(file) {
    if (!file) return null;
    if (!file.type.startsWith("image/") || !ALLOWED_IMAGE_EXT.test(file.name)) {
      return "Images must be PNG, JPG, GIF, or WebP.";
    }
    if (file.size > MAX_IMAGE_BYTES) {
      return `"${file.name}" is larger than 10 MB.`;
    }
    return null;
  }

  // Clear a field's error as soon as the user edits it
  if (listingForm) {
    listingForm.addEventListener("input", (event) => {
      const field = event.target;
      if (field.getAttribute("aria-invalid") === "true") {
        field.removeAttribute("aria-invalid");
        const describedBy = field.getAttribute("aria-describedby");
        if (describedBy) document.getElementById(describedBy)?.remove();
      }
    });
  }

  // Returns the FormData to send, or null if anything is invalid (errors are shown).
  function validateAndBuildFormData() {
    clearErrors();
    const errors = [];

    const storefrontSelectEl = document.getElementById("storefrontSelect");
    const titleInput = document.getElementById("listingName");
    const priceInput = document.getElementById("price");
    const imageHelper = document.getElementById("imageHelperText");
    const sizesLabel = document.querySelector(".category-card .section-label");
    const isOneSizeMode = oneSizeToggle && oneSizeToggle.checked;
    const isMadeToOrder = madeToOrderToggle && madeToOrderToggle.checked;

    const fail = (anchor, message, field) => {
      showFieldError(anchor, message, field);
      errors.push({ message, focus: field || anchor });
    };

    // Images
    const listingImages = selectedListingImages.filter(Boolean);
    if (listingImages.length === 0) {
      fail(imageHelper, "Please add at least one listing image.", null);
    } else {
      const badImage = listingImages.map(validateImageFile).find(Boolean);
      if (badImage) fail(imageHelper, badImage, null);
    }

    // Storefront
    const storefrontId = storefrontSelectEl ? storefrontSelectEl.value : "";
    if (!storefrontId) {
      fail(storefrontSelectEl, "Please select a storefront for this listing.");
    }

    // Title
    const listingName = titleInput.value.trim();
    if (!listingName) {
      fail(titleInput, "Listing name is required.");
    } else if (listingName.length > MAX_TITLE_LENGTH) {
      fail(titleInput, `Listing name must be ${MAX_TITLE_LENGTH} characters or fewer.`);
    }

    // Price: required, 0 or more, at most 2 decimals
    const priceText = priceInput.value.trim();
    const price = Number(priceText);
    const priceAnchor = priceInput.closest(".price-wrap") || priceInput;
    if (!priceText) {
      fail(priceAnchor, "Price is required.", priceInput);
    } else if (!Number.isFinite(price) || price < 0) {
      fail(priceAnchor, "Price must be a number of $0.00 or more.", priceInput);
    } else if (price > MAX_PRICE) {
      fail(priceAnchor, "Price is too high.", priceInput);
    } else if (!/^\d+(\.\d{1,2})?$/.test(priceText)) {
      fail(priceAnchor, "Price can have at most 2 decimal places (e.g. 24.99).", priceInput);
    }

    // Sizes + quantities
    let sizes = [];
    const sizeQuantities = {};

    if (isOneSizeMode) {
      sizes = ["One Size"];
      if (isMadeToOrder) {
        sizeQuantities["One Size"] = 0;
      } else {
        const qty = parseWholeNumber(oneSizeQty ? oneSizeQty.value : "");
        if (isNaN(qty) || qty > MAX_QTY) {
          fail(oneSizeQty, "Enter a whole number quantity (0 or more).");
        } else {
          sizeQuantities["One Size"] = qty;
        }
      }
    } else {
      sizes = Array.from(document.querySelectorAll("input[name='sizes']:checked")).map((cb) => cb.value);
      if (sizes.length === 0) {
        fail(sizesLabel, "Select at least one size, or turn on One Size.", null);
      }
      for (const size of sizes) {
        const qtyInput = multiSizeGrid
          ? multiSizeGrid.querySelector(`.size-qty-input[data-size="${size}"]`)
          : null;
        if (isMadeToOrder) {
          sizeQuantities[size] = 0;
          continue;
        }
        const qty = parseWholeNumber(qtyInput ? qtyInput.value : "");
        if (isNaN(qty) || qty > MAX_QTY) {
          fail(qtyInput?.closest(".size-qty-row") || qtyInput, `Enter a whole number quantity for size ${size}.`, qtyInput);
        } else {
          sizeQuantities[size] = qty;
        }
      }
    }

    const totalQty = isMadeToOrder ? 0 : Object.values(sizeQuantities).reduce((a, b) => a + b, 0);

    // A brand-new in-stock listing with 0 items would be created as SOLD OUT
    const quantitiesAllValid = Object.keys(sizeQuantities).length === sizes.length && sizes.length > 0;
    if (!isMadeToOrder && quantitiesAllValid && totalQty === 0) {
      fail(sizesLabel, "Total quantity is 0, so the listing would show as sold out. Add stock or turn on Made to Order.", null);
    }

    if (errors.length > 0) {
      showSummary(errors.length === 1
        ? "Please fix the highlighted field."
        : `Please fix the ${errors.length} highlighted fields.`);
      const first = errors[0].focus;
      if (first) {
        first.scrollIntoView({ behavior: "smooth", block: "center" });
        if (typeof first.focus === "function") first.focus({ preventScroll: true });
      }
      return null;
    }

    const formData = new FormData();
    formData.append("storefront_id", storefrontId);
    formData.append("title", listingName);
    formData.append("quantity_on_hand", totalQty);
    formData.append("price", priceText);
    formData.append("fulfillment_type", "IN_STOCK");
    formData.append("status", "ACTIVE");
    formData.append("is_made_to_order", isMadeToOrder ? "true" : "false");
    formData.append("sizes_available", JSON.stringify(sizes));
    formData.append("size_quantities", JSON.stringify(sizeQuantities));
    listingImages.forEach((file) => formData.append("listing_images", file));
    return { formData, listingName };
  }

  function setSubmitting(submitting) {
    isSubmitting = submitting;
    if (submitBtn) {
      submitBtn.disabled = submitting;
      submitBtn.textContent = submitting ? "Creating..." : "Create Listing";
    }
  }

  // ── Form submission ──────────────────────────────────────────

  if (listingForm) {
    listingForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (isSubmitting) return; // double-click would otherwise create two listings

      const validated = validateAndBuildFormData();
      if (!validated) return;

      setSubmitting(true);
      try {
        const userRes = await fetch("/auth/api/auth/me");
        if (!userRes.ok) {
          showSummary("Your session has ended. Redirecting you to log in...");
          window.setTimeout(() => { window.location.href = "/auth/login"; }, 1500);
          return;
        }
        const user = await userRes.json();

        const response = await fetch("/api/listings/create", {
          method: "POST",
          headers: {
            "X-User-Id": user.id,
            "X-User-Role": user.role
          },
          body: validated.formData,
        });

        const result = await response.json().catch(() => ({}));

        if (response.ok) {
          showListingToast(`Listing "${validated.listingName}" created successfully!`);
          window.setTimeout(() => {
            window.location.href = "/my-storefront";
          }, 2500);
          return; // keep the button disabled while we redirect
        }
        showSummary(result.error || "Something went wrong creating the listing. Please try again.");
        showListingToast(result.error || "Could not create listing.", "error");
      } catch (error) {
        console.error("Error submitting form:", error);
        showSummary("Couldn't reach the server. Check your connection and try again.");
      }
      setSubmitting(false);
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      window.location.href = "/storefronts";
    });
  }

  async function loadUserStorefronts() {
    try {
      const userRes = await fetch("/auth/api/auth/me");
      if (!userRes.ok) {
        window.location.href = "/auth/login";
        return;
      }
      const user = await userRes.json();

      const response = await fetch("/api/storefronts/me", {
        method: "GET",
        headers: {
          "X-User-Id": user.id,
          "X-User-Role": user.role
        },
      });

      if (response.ok) {
        const storefrontData = await response.json();
        const storefronts = Array.isArray(storefrontData)
          ? storefrontData
          : storefrontData && storefrontData.id
            ? [storefrontData]
            : [];

        storefrontSelect.innerHTML = "";

        if (storefronts.length > 0) {
          const defaultOption = document.createElement("option");
          defaultOption.value = "";
          defaultOption.textContent = "Select a storefront";
          defaultOption.disabled = true;
          defaultOption.selected = true;
          storefrontSelect.appendChild(defaultOption);

          storefronts.forEach(storefront => {
            const option = document.createElement("option");
            option.value = storefront.id;
            option.textContent = storefront.brand_name || storefront.name || `Storefront #${storefront.id}`;
            storefrontSelect.appendChild(option);
          });

          // users have one storefront, so select it
          if (storefronts.length === 1) {
            storefrontSelect.value = String(storefronts[0].id);
          }
        } else {
          storefrontSelect.innerHTML = '<option value="" disabled>No storefronts found - create one first</option>';
          if (listingForm) {
            listingForm.querySelectorAll("input, select, button[type='submit']").forEach(el => {
              el.disabled = true;
            });
          }
          const messageDiv = document.createElement("div");
          messageDiv.style.cssText = "color: #9fd0ff; margin-top: 10px; font-weight: bold; text-align:center;";
          messageDiv.innerHTML = `You must create a storefront before creating listings. <a href="/storefronts/create" style="color:#fff; text-decoration:underline;">Create one here</a>`;
          storefrontSelect.parentNode.appendChild(messageDiv);
        }
      } else if (response.status === 404) {
        storefrontSelect.innerHTML = '<option value="" disabled>No storefronts found - create one first</option>';
        if (listingForm) {
          listingForm.querySelectorAll("input, select, button[type='submit']").forEach(el => {
            el.disabled = true;
          });
        }
        const messageDiv = document.createElement("div");
        messageDiv.style.cssText = "color: #9fd0ff; margin-top: 10px; font-weight: bold; text-align:center;";
        messageDiv.innerHTML = `You must create a storefront before creating listings. <a href="/storefronts/create" style="color:#fff; text-decoration:underline;">Create one here</a>`;
        storefrontSelect.parentNode.appendChild(messageDiv);
      } else {
        console.error("Failed to load storefronts");
        storefrontSelect.innerHTML = '<option value="">Error loading storefronts</option>';
      }
    } catch (error) {
      console.error("Error loading storefronts:", error);
      storefrontSelect.innerHTML = '<option value="">Error loading storefronts</option>';
    }
  }
});
