/*
    checkout.js
    The Pirate Cove Campus Marketplace
    CSC 405 Sp 26'
    Updated by Day Ekoi - 4/22/26
    - Reads cart from session via /auth/cart/json
    - Displays items with size, qty, and subtotals
    - Submits buyer details to /api/checkout/complete
    - Redirects to order confirmation on success
*/

document.addEventListener("DOMContentLoaded", async () => {
    const itemsList = document.getElementById("checkoutItemsList");
    const totalDisplay = document.querySelector(".total-amount");
    const submitBtn = document.getElementById("submitCheckoutBtn");
    const errorMsg = document.getElementById("checkoutError");

    function showError(msg) {
        if (!errorMsg) return;
        errorMsg.textContent = msg;
        errorMsg.style.display = "block";
        errorMsg.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideError() {
        if (errorMsg) errorMsg.style.display = "none";
    }

    // Load cart from Flask session
    let cart = [];
    try {
        const res = await fetch("/auth/cart/json");
        if (res.ok) cart = await res.json();
    } catch (e) {
        console.error("Failed to load cart:", e);
    }

    if (!Array.isArray(cart) || cart.length === 0) {
        if (itemsList) itemsList.innerHTML = '<p class="helper-text">Your bag is currently empty.</p>';
        if (totalDisplay) totalDisplay.textContent = "$0.00";
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Cart is Empty";
        }
        return;
    }

    // Render cart items in order summary
    let total = 0;
    if (itemsList) {
        itemsList.innerHTML = "";
        cart.forEach((item) => {
            const price = parseFloat(item.price || 0);
            const qty = parseInt(item.quantity || 1, 10);
            const subtotal = price * qty;
            total += subtotal;

            const row = document.createElement("div");
            row.className = "summary-row";
            row.innerHTML = `
                <div>
                    <div class="summary-name">${item.name || "Item"}</div>
                    <div class="summary-meta">
                        ${item.size ? `Size: ${item.size} &nbsp;|&nbsp; ` : ""}Qty: ${qty}
                    </div>
                </div>
                <span class="summary-price">$${subtotal.toFixed(2)}</span>
            `;
            itemsList.appendChild(row);
        });
    }

    if (totalDisplay) totalDisplay.textContent = `$${total.toFixed(2)}`;

    // Handle form submission
    const form = document.getElementById("checkoutForm");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideError();

        const firstName = (document.getElementById("firstName")?.value || "").trim();
        const lastName = (document.getElementById("lastName")?.value || "").trim();
        const email = (document.getElementById("buyerEmail")?.value || "").trim();
        const contact = (document.getElementById("contactNumber")?.value || "").trim();
        const meetingLocation = (document.getElementById("meetingLocation")?.value || "").trim();

        if (!firstName || !lastName || !email || !contact || !meetingLocation) {
            showError("All fields are required to complete your transaction.");
            return;
        }

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Processing...";
        }

        try {
            const res = await fetch("/api/checkout/create-session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    email,
                    contact,
                    meeting_location: meetingLocation,
                }),
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.error || "Transaction failed.");
            }

            window.location.href = data.url;
        } catch (err) {
            showError(err.message || "Something went wrong. Please try again.");
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = "Complete Transaction";
            }
        }
    });
});
