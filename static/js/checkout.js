/*
    checkout.js
    The Pirate Cove Campus Marketplace
    CSC 405 Sp 26'
    Updated by Day Ekoi - 4/22/26
    - Reads cart from session via /auth/cart/json
    - Displays items with size, qty, and subtotals
    - Redirects to order confirmation on success
    Stripe test-mode redirect by Tykeara Hammond 10/18/26
    Updated by Anthony Jackson - Iteration 4 (11/11/26)
    - Two payment choices: "Pay in person" (default, POST /api/checkout/complete) and the optional
      Stripe TEST card checkout (POST /api/checkout/create-session), shown only when
      /api/checkout/options says Stripe test mode is on.
    - Item names/sizes are shown as text, not HTML (a seller could put HTML in a listing title).
    - The total shown here is a preview; the server recalculates it from the listing prices.
*/

document.addEventListener("DOMContentLoaded", async () => {
    const itemsList = document.getElementById("checkoutItemsList");
    const totalDisplay = document.querySelector(".total-amount");
    const submitBtn = document.getElementById("submitCheckoutBtn");
    const errorMsg = document.getElementById("checkoutError");
    const stripeOption = document.getElementById("stripeOption");
    const paymentNote = document.getElementById("paymentNote");

    function showError(msg) {
        if (!errorMsg) return;
        errorMsg.textContent = msg;
        errorMsg.style.display = "block";
        errorMsg.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideError() {
        if (errorMsg) errorMsg.style.display = "none";
    }

    function selectedPayment() {
        const picked = document.querySelector('input[name="paymentMethod"]:checked');
        return picked ? picked.value : "in_person";
    }

    function setButtonText() {
        if (!submitBtn || submitBtn.disabled) return;
        submitBtn.textContent = selectedPayment() === "stripe_test" ? "Pay with Test Card" : "Place Order";
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

    // Show the Stripe option only if the server has a Stripe TEST key
    try {
        const res = await fetch("/api/checkout/options");
        if (res.ok) {
            const options = await res.json();
            if (options.stripe_test && stripeOption) stripeOption.style.display = "block";
        }
    } catch (e) {
        console.warn("Could not load payment options; using pay in person.", e);
    }
    document.querySelectorAll('input[name="paymentMethod"]').forEach((radio) => {
        radio.addEventListener("change", () => {
            if (paymentNote) {
                paymentNote.textContent = selectedPayment() === "stripe_test"
                    ? "You'll go to Stripe's test checkout. Use card 4242 4242 4242 4242. No real money moves."
                    : "No card is charged online. You pay the seller when you meet.";
            }
            setButtonText();
        });
    });
    setButtonText();

    // Render cart items in order summary (built with textContent so names can't inject HTML)
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

            const left = document.createElement("div");
            const name = document.createElement("div");
            name.className = "summary-name";
            name.textContent = item.name || "Item";
            const meta = document.createElement("div");
            meta.className = "summary-meta";
            meta.textContent = (item.size ? `Size: ${item.size}  |  ` : "") + `Qty: ${qty}`;
            left.append(name, meta);

            const priceEl = document.createElement("span");
            priceEl.className = "summary-price";
            priceEl.textContent = `$${subtotal.toFixed(2)}`;

            row.append(left, priceEl);
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

        const useStripe = selectedPayment() === "stripe_test";
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Processing...";
        }

        try {
            const res = await fetch(useStripe ? "/api/checkout/create-session" : "/api/checkout/complete", {
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

            if (useStripe) {
                window.location.href = data.url;   // Stripe's hosted test checkout
            } else {
                window.location.href = `/order-confirmation?conf=${encodeURIComponent(data.confirmation_number)}`;
            }
        } catch (err) {
            showError(err.message || "Something went wrong. Please try again.");
            if (submitBtn) {
                submitBtn.disabled = false;
                setButtonText();
            }
        }
    });
});
