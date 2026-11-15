/* Made by Jaylen Belle 11/12/2026 
This file runs the setting tab on the account page. It loads the account summary and lets the user change their password.
*/




(function () {
    const summaryMessage = document.getElementById("settingsMessage");
    const form = document.getElementById("passwordForm");
    if (!form) return;


    const message = document.getElementById("passwordMessage");
    const saveButton = document.getElementById("passwordSaveButton");
    const showBox = document.getElementById("showPassword");
    const FIELDS = ["current_password", "new_password", "confirm_password"];


    //Displays a message and marks it red as an error when needed.
    function setMessage(el, text, isError) {
        el.textContent = text;
        el.classList.toggle("error", !!isError);
    }


    //Puts text into an element by its id.
    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }



    //Formats a date as a readable US date string.
    function formatDate(value) {
        if (!value) return "-";
        let x = new Date(value);
        if(isNaN(x)) x = new Date(value + "T00:00:00");
        if (isNaN(x)) return "-";
        return x.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
    }
   


    //loads the account summary and fills the boxes with the user's information.
    async function LoadSettings() {
        try {
            const response = await fetch("/api/account/settings");
            if (response.status === 401) {setMessage(summaryMessage, "Log in to see your account settings.", true); return; }
            if (!response.ok) throw new Error();
            const x = await response.json();
            setText("stUsername", x.username);
            setText("stEmail", x.email);
            setText("stRole", x.role === "admin" ? "Admin" : (x.has_storefront ? "Seller" : "Student"));
            setText("stCreatedAt", formatDate(x.created_at));
            setText("stListings", String(x.listings_count));
            setText("stWishlist", String(x.wishlist_count));
            setText("stOrders", String(x.orders_count));
        } catch (error) {
            setMessage(summaryMessage, "Unable to load your account settings. Refresh the page.", true);
        }
    }

    //Shows or hides the password fields from hidden to visible text.
    showBox.addEventListener("change", () => {
        FIELDS.forEach(name => {form.elements[name].type = showBox.checked ? "text" : "password";});

    });

    //Sends the password change request and displays the result when a user clicks change password.
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        form.querySelectorAll(".profile-row").forEach(row => row.classList.remove("has-error"));
        setMessage(message, "Saving....", false);
        saveButton.disabled = true;

        //Builds the request body with the values from the password fields.
        const body = {};
        FIELDS.forEach(name => { body[name] = form.elements[name].value; });

        //Sends the password change request to the server as json.
        try {
            const response = await fetch("/api/account/password", { 
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });


            const data = await response.json().catch(() => ({}));
            if (response.ok) {
                form.reset();
                FIELDS.forEach(name => { form.elements[name].type = "password"; });
                setMessage(message, data.message || "Your password has been updated.", false);
            } else {
                if (data.field && form.elements[data.field]) {
                    form.elements[data.field].closest(".profile-row").classList.add("has-error");
                    form.elements[data.field].focus();
                }
                setMessage(message, data.error || "We couldn't change your password. Try again.", true);
            }
        //The request needs to reach the server.
        } catch (error) {
            setMessage(message, "We couldn't change your password. Please try again.", true);
        } finally {
            saveButton.disabled = false;
        }
    });
    
    //Loads the summary when the page loads.
    document.addEventListener("DOMContentLoaded", LoadSettings);


})();
        






