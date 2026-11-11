// File Created By David Jackson
// Updated by Ethan Williams 11/9/26:
// - every value from the database is escaped before it goes into the page (no HTML injection)
// - deletes ask for confirmation and show the server's error message if they fail
// - all four tables load when the page opens; the buttons reload them
// - an expired session sends the admin back to the admin log in page

const statusBox = () => document.getElementById("adminStatus");

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function showStatus(message, isError = false) {
    const box = statusBox();
    if (!box) return;
    box.textContent = message;
    box.classList.toggle("error", isError);
    box.hidden = !message;
}

function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    return isNaN(date) ? value : date.toLocaleString();
}

// Only allow http(s) links and site-relative paths in hrefs (blocks javascript: URLs)
function safeUrl(value) {
    const url = String(value || "");
    return /^(https?:\/\/|\/)/i.test(url) ? url : "";
}

/*
 * Calls an admin API route and returns the parsed JSON.
 * Throws an Error with the server's message when the request fails.
 */
async function adminRequest(url, options = {}) {
    const response = await fetch(url, options);

    // Logged out, timed out, or not an admin: 401, a redirect to a log in page, or a 403 on a page load.
    // (A 403 on a DELETE is a real answer, e.g. "can't delete an admin", so it is shown instead.)
    const isRead = !options.method || options.method === "GET";
    if (response.status === 401 || response.redirected || (response.status === 403 && isRead)) {
        window.location.href = "/auth/admin-login";
        throw new Error("Your session has ended. Please log in again.");
    }

    let data = null;
    try {
        data = await response.json();
    } catch (e) {
        data = null;
    }

    if (!response.ok) {
        throw new Error((data && data.error) || `Request failed (${response.status})`);
    }
    return data;
}

/*
 * Loads rows into a table body. buildRow(item) returns the <tr> inner HTML.
 */
async function fillTable(tableId, url, columnCount, buildRow, emptyText) {
    const body = document.querySelector(`#${tableId} tbody`);
    body.innerHTML = `<tr><td colspan="${columnCount}">Loading…</td></tr>`;

    try {
        const items = await adminRequest(url);
        if (!items || items.length === 0) {
            body.innerHTML = `<tr><td colspan="${columnCount}">${emptyText}</td></tr>`;
            return;
        }
        body.innerHTML = items.map(item => `<tr>${buildRow(item)}</tr>`).join("");
    } catch (error) {
        body.innerHTML = `<tr><td colspan="${columnCount}">Could not load.</td></tr>`;
        showStatus(error.message, true);
    }
}

/*
 * Confirms, sends a DELETE, shows the result, then reloads the table.
 */
async function confirmAndDelete(url, question, reload) {
    if (!window.confirm(question)) return;

    try {
        const result = await adminRequest(url, { method: "DELETE" });
        showStatus((result && result.message) || "Deleted.");
    } catch (error) {
        showStatus(error.message, true);
    }
    reload();
}


// USERS SECTION  (GET /admin/users, DELETE /admin/users/<id>)

function loadUsers() {
    return fillTable("usersTable", "/admin/users", 6, user => {
        const isAdmin = (user.role || "").toLowerCase() === "admin";
        return `
            <td>${escapeHtml(user.id)}</td>
            <td>${escapeHtml(user.username)}</td>
            <td>${escapeHtml(user.email)}</td>
            <td>${escapeHtml(user.role || "user")}</td>
            <td>${escapeHtml(formatDate(user.created_at))}</td>
            <td>${isAdmin
                ? "<small>Admin</small>"
                : `<button class="delete" data-action="delete-user" data-id="${escapeHtml(user.id)}" data-name="${escapeHtml(user.username)}">Delete</button>`}
            </td>`;
    }, "No users yet.");
}

function deleteUser(userId, username) {
    return confirmAndDelete(
        `/admin/users/${encodeURIComponent(userId)}`,
        `Delete user "${username || userId}"? This also removes their storefronts, listings and messages and cannot be undone.`,
        loadUsers
    );
}


// LISTINGS SECTION  (GET /admin/listings, DELETE /admin/listings/<id> = soft delete)

function loadListings() {
    return fillTable("listingsTable", "/admin/listings", 9, listing => {
        const deleted = (listing.status || "").toUpperCase() === "DELETED";
        const price = listing.price == null ? "" : `$${Number(listing.price).toFixed(2)}`;
        return `
            <td>${escapeHtml(listing.id)}</td>
            <td>${escapeHtml(listing.storefront_id)}</td>
            <td>${escapeHtml(listing.title)}</td>
            <td>${escapeHtml(price)}</td>
            <td>${escapeHtml(listing.quantity_on_hand)}</td>
            <td>${escapeHtml(listing.status || "ACTIVE")}</td>
            <td>${escapeHtml(listing.fulfillment_type)}</td>
            <td>${escapeHtml(formatDate(listing.created_at))}</td>
            <td>${deleted
                ? "<small>Deleted</small>"
                : `<button class="delete" data-action="delete-listing" data-id="${escapeHtml(listing.id)}" data-name="${escapeHtml(listing.title)}">Delete</button>`}
            </td>`;
    }, "No listings yet.");
}

function deleteListing(listingId, title) {
    return confirmAndDelete(
        `/admin/listings/${encodeURIComponent(listingId)}`,
        `Remove listing "${title || listingId}" from the marketplace?`,
        loadListings
    );
}


// STOREFRONTS SECTION  (GET /admin/storefronts, DELETE /admin/storefronts/<id>)

function loadStorefronts() {
    return fillTable("storefrontsTable", "/admin/storefronts", 6, store => `
            <td>${escapeHtml(store.id)}</td>
            <td>${escapeHtml(store.brand_name || store.name)}</td>
            <td>${escapeHtml(store.owner_id)}</td>
            <td>${store.is_active === false ? "No" : "Yes"}</td>
            <td>${escapeHtml(store.item_count ?? 0)}</td>
            <td><button class="delete" data-action="delete-storefront" data-id="${escapeHtml(store.id)}" data-name="${escapeHtml(store.brand_name || store.name)}">Delete</button></td>`,
        "No storefronts yet.");
}

function deleteStorefront(storeId, name) {
    return confirmAndDelete(
        `/admin/storefronts/${encodeURIComponent(storeId)}`,
        `Delete storefront "${name || storeId}" and all of its listings? This cannot be undone.`,
        loadStorefronts
    );
}


// RETURNS SECTION  (GET /admin/returns, PATCH /admin/returns/<id>)

const RETURN_STATUSES = ["pending", "reviewed", "resolved"];

function loadReturns() {
    return fillTable("returnsTable", "/admin/returns", 7, item => {
        const imageUrl = safeUrl(item.damage_image_url);
        const options = RETURN_STATUSES.map(status =>
            `<option value="${status}" ${item.status === status ? "selected" : ""}>${status[0].toUpperCase() + status.slice(1)}</option>`
        ).join("");
        return `
            <td>${escapeHtml(item.id)}</td>
            <td>${escapeHtml(item.username)}<br><small>${escapeHtml(item.email)}</small></td>
            <td>${escapeHtml(item.order_number)}</td>
            <td>${item.has_damage ? "Yes" : "No"}</td>
            <td>${imageUrl ? `<a href="${escapeHtml(imageUrl)}" target="_blank" rel="noopener noreferrer">View</a>` : "—"}</td>
            <td>
                <select data-return-id="${escapeHtml(item.id)}">${options}</select>
                <button data-action="save-return" data-id="${escapeHtml(item.id)}">Save</button>
            </td>
            <td>${escapeHtml(item.reason)}</td>`;
    }, "No return requests.");
}

async function saveReturnStatus(returnId) {
    const select = document.querySelector(`select[data-return-id="${CSS.escape(String(returnId))}"]`);
    if (!select) return;

    try {
        await adminRequest(`/admin/returns/${encodeURIComponent(returnId)}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: select.value })
        });
        showStatus(`Return #${returnId} marked ${select.value}.`);
    } catch (error) {
        showStatus(error.message, true);
    }
    loadReturns();
}


// One click handler for every row button (data-action), so no inline onclick with database values
document.addEventListener("click", event => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const { action, id, name } = button.dataset;
    if (action === "delete-user") deleteUser(id, name);
    else if (action === "delete-listing") deleteListing(id, name);
    else if (action === "delete-storefront") deleteStorefront(id, name);
    else if (action === "save-return") saveReturnStatus(id);
});

document.addEventListener("DOMContentLoaded", () => {
    loadUsers();
    loadListings();
    loadStorefronts();
    loadReturns();
});
