
/*
 * THE PIRATE COVE - Automatic Session Timeout
 * Security Enhancement Added by Nicholas Smith
 * Date: October 25, 2026
 *
 * Logs users out after 5 minutes without activity.
 * Detects mouse, keyboard, scroll, and touch activity.
 */

(function () {
    "use strict";

    const IDLE_LIMIT = 5 * 60 * 1000;
    const CHECK_INTERVAL = 1000;
    const HEARTBEAT_INTERVAL = 15000;
    const STORAGE_KEY = "thevault_last_input";

    let lastInput = Number(localStorage.getItem(STORAGE_KEY));
    let lastHeartbeat = 0;
    let lastRecorded = 0;
    let loggingOut = false;

    // Redirect to the existing Flask logout route.
    function logoutUser() {
        if (loggingOut) return;
        loggingOut = true;

        localStorage.removeItem(STORAGE_KEY);
        window.location.replace("/auth/logout");
    }

    // Keep the server updated only while the user is active.
    async function sendHeartbeat() {
        if (loggingOut) return;

        const now = Date.now();

        if (now - lastHeartbeat < HEARTBEAT_INTERVAL) {
            return;
        }

        lastHeartbeat = now;

        try {
            const response = await fetch("/auth/activity", {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store"
            });

            if (response.status === 401) {
                logoutUser();
            }
        } catch (error) {
            console.warn("Activity update failed:", error);
        }
    }

    // Run whenever genuine activity is detected.
    function recordActivity() {
        if (loggingOut) return;

        const now = Date.now();

        // Never revive a session that has already timed out.
        const stored = Number(
            localStorage.getItem(STORAGE_KEY)
        );

        if (!stored || now - stored >= IDLE_LIMIT) {
            logoutUser();
            return;
        }

        // Limit frequent mouse movement updates.
        if (now - lastRecorded >= 1000) {
            lastInput = now;
            lastRecorded = now;
            localStorage.setItem(STORAGE_KEY, String(now));
        }

        sendHeartbeat();
    }

    // Detect keyboard and mouse activity.
    const events = [
        "mousemove",
        "mousedown",
        "keydown",
        "wheel",
        "touchstart"
    ];

    events.forEach(function (eventName) {
        document.addEventListener(
            eventName,
            recordActivity,
            { passive: true }
        );
    });

    // Synchronize activity across browser tabs.
    window.addEventListener("storage", function (event) {
        if (event.key === STORAGE_KEY) {
            if (event.newValue === null) {
                logoutUser();
            } else {
                lastInput = Number(event.newValue);
            }
        }
    });

    // Check for inactivity every second.
    setInterval(function () {
        if (loggingOut) return;

        const stored = Number(
            localStorage.getItem(STORAGE_KEY)
        );

        if (!stored || Date.now() - stored >= IDLE_LIMIT) {
            logoutUser();
        }
    }, CHECK_INTERVAL);

    // Check when returning to a background tab.
    document.addEventListener("visibilitychange", function () {
        if (!document.hidden && !loggingOut) {
            const stored = Number(
                localStorage.getItem(STORAGE_KEY)
            );

            if (!stored ||
                Date.now() - stored >= IDLE_LIMIT) {
                logoutUser();
            }
        }
    });

    // Do not reset the timer just because a page loads.
    // app.py initializes it after a successful login.
    if (!lastInput ||
        Date.now() - lastInput >= IDLE_LIMIT) {
        logoutUser();
    }
})();
