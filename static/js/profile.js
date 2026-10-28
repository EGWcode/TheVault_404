/*
    profile.js
    Made by Anthony Jackson 10/21/26

    Runs the Profile tab on the Account page. It loads the user's optional info
    (first name, last name, phone, class year, hometown), and saves it when they
    click Save. Nothing here is required, and it's only on the Account page,
    not at signup or login.

    It talks to the routes in controllers/profile_controller.py.
*/

(function () {
  const form = document.getElementById("profileForm");
  if (!form) return;

  const msg = document.getElementById("profileMsg");
  const saveBtn = document.getElementById("profileSaveBtn");
  const who = document.getElementById("profileWho");

  const FIELDS = ["first_name", "last_name", "phone", "class_year", "hometown"];

  function setMessage(text, isError) {
    msg.textContent = text;
    msg.classList.toggle("error", !!isError);
  }

  function clearErrors() {
    form.querySelectorAll(".profile-row").forEach(row => row.classList.remove("has-error"));
  }

  function fillForm(profile) {
    FIELDS.forEach(name => {
      const input = form.elements[name];
      if (input) input.value = profile[name] || "";
    });
    if (who && profile.username) {
      who.textContent = `Signed in as ${profile.username} (${profile.email})`;
    }
  }

  async function loadProfile() {
    try {
      const res = await fetch("/api/profile");
      if (res.status === 401) { setMessage("Log in to see your profile.", true); return; }
      if (!res.ok) throw new Error();
      fillForm(await res.json());
    } catch (err) {
      setMessage("We couldn't load your profile. Try refreshing the page.", true);
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();
    setMessage("Saving...", false);
    saveBtn.disabled = true;

    const body = {};
    FIELDS.forEach(name => { body[name] = form.elements[name].value; });

    try {
      const res = await fetch("/api/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        fillForm(data);
        setMessage("Saved. Your profile is updated.", false);
      } else {
        if (data.field && form.elements[data.field]) {
          form.elements[data.field].closest(".profile-row").classList.add("has-error");
        }
        setMessage(data.error || "We couldn't save your profile. Try again.", true);
      }
    } catch (err) {
      setMessage("We couldn't save your profile. Check your connection and try again.", true);
    } finally {
      saveBtn.disabled = false;
    }
  });

  document.addEventListener("DOMContentLoaded", loadProfile);
})();
