/*
    messages.js

    The Pirate Cove Campus Marketplace
    CSC 405 Sp 26'
    Created by Ethan Williams 10/20/26

Messages page: inbox, conversations, sending, and polling for new messages.
*/

const THREAD_POLL_MS = 3000;
const INBOX_POLL_MS = 10000;

const page = document.getElementById("messagesPage");
const inboxList = document.getElementById("inboxList");
const inboxEmpty = document.getElementById("inboxEmpty");
const threadPlaceholder = document.getElementById("threadPlaceholder");
const threadInner = document.getElementById("threadInner");
const threadName = document.getElementById("threadName");
const threadAbout = document.getElementById("threadAbout");
const threadStoreLink = document.getElementById("threadStoreLink");
const threadMessages = document.getElementById("threadMessages");
const threadBack = document.getElementById("threadBack");
const composer = document.getElementById("composer");
const composerInput = document.getElementById("composerInput");
const composerSend = document.getElementById("composerSend");
const composerError = document.getElementById("composerError");

const state = {
    conversations: [],
    active: null,          // details of the open conversation
    myId: null,            // current user's id, from the open conversation
    lastMessageId: 0,      // newest message id shown, used for ?after=
    shownIds: new Set(),   // prevents duplicates
    lastDayShown: null,    // for date dividers
    loadingThread: false,
};


// helpers

async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        ...options,
    });
    if (response.status === 401) {
        window.location.href = "/auth/login";
        throw new Error("Not logged in");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const error = new Error(data.error || "Something went wrong");
        error.status = response.status;
        throw error;
    }
    return data;
}

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
}

function formatTime(iso) {
    return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatDay(iso) {
    const date = new Date(iso);
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    if (date.toDateString() === today.toDateString()) return "Today";
    if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
    return date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
}

function formatInboxTime(iso) {
    if (!iso) return "";
    const day = formatDay(iso);
    return day === "Today" ? formatTime(iso) : day;
}

function aboutText(conversation) {
    if (conversation.listing_title) return `About: ${conversation.listing_title}`;
    return conversation.role === "seller" ? `Your storefront: ${conversation.brand_name}` : "General question";
}

function setUrlConversation(id) {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("c", id);
    else url.searchParams.delete("c");
    history.replaceState(null, "", url);
}


// inbox

function renderInbox() {
    inboxList.textContent = "";
    inboxEmpty.hidden = state.conversations.length > 0;

    state.conversations.forEach((conversation) => {
        const item = el("li");
        const button = el("button", "inbox-item");
        button.type = "button";
        if (state.active && state.active.id === conversation.id) button.classList.add("active");
        if (conversation.unread > 0) button.classList.add("unread");

        // logo for buyers, initial for sellers
        let avatar;
        if (conversation.role === "buyer" && conversation.logo_url) {
            avatar = el("img", "inbox-avatar");
            avatar.src = conversation.logo_url;
            avatar.alt = "";
        } else {
            avatar = el("span", "inbox-avatar", (conversation.other_name || "?").charAt(0).toUpperCase());
        }

        const text = el("span", "inbox-text");
        const top = el("span", "inbox-top");
        top.append(
            el("span", "inbox-name", conversation.other_name),
            el("span", "inbox-time", formatInboxTime(conversation.last_message_at))
        );
        const youPrefix = conversation.last_sender_id === conversation[conversation.role === "buyer" ? "buyer_id" : "seller_id"] ? "You: " : "";
        text.append(
            top,
            el("span", "inbox-about", aboutText(conversation)),
            el("span", "inbox-preview", youPrefix + (conversation.last_message || ""))
        );

        button.append(avatar, text);
        if (conversation.unread > 0) {
            button.append(el("span", "inbox-badge", conversation.unread > 99 ? "99+" : String(conversation.unread)));
        }
        button.addEventListener("click", () => openConversation(conversation.id));

        item.append(button);
        inboxList.append(item);
    });
}

async function loadInbox() {
    try {
        const data = await api("/api/conversations");
        state.conversations = data.conversations || [];
        // open conversation is already read
        if (state.active) {
            const open = state.conversations.find((c) => c.id === state.active.id);
            if (open) open.unread = 0;
        }
        renderInbox();
    } catch (error) {
        console.error("Could not load conversations:", error);
    }
}


// conversation

function appendMessages(messages) {
    if (!messages.length) return;

    const nearBottom = threadMessages.scrollHeight - threadMessages.scrollTop - threadMessages.clientHeight < 80;
    const emptyNote = threadMessages.querySelector(".thread-empty");
    if (emptyNote) emptyNote.remove();

    messages.forEach((message) => {
        if (state.shownIds.has(message.id)) return;
        state.shownIds.add(message.id);
        state.lastMessageId = Math.max(state.lastMessageId, message.id);

        const day = formatDay(message.created_at);
        if (day !== state.lastDayShown) {
            threadMessages.append(el("div", "day-divider", day));
            state.lastDayShown = day;
        }

        const bubble = el("div", `bubble ${message.sender_id === state.myId ? "mine" : "theirs"}`);
        bubble.append(el("span", "bubble-body", message.body), el("span", "bubble-time", formatTime(message.created_at)));
        threadMessages.append(bubble);
    });

    if (nearBottom || state.loadingThread) {
        threadMessages.scrollTop = threadMessages.scrollHeight;
    }
}

async function openConversation(conversationId) {
    state.loadingThread = true;
    composerError.textContent = "";

    try {
        const { conversation } = await api(`/api/conversations/${conversationId}`);
        state.active = conversation;
        state.myId = conversation.role === "buyer" ? conversation.buyer_id : conversation.seller_id;
        state.lastMessageId = 0;
        state.shownIds = new Set();
        state.lastDayShown = null;

        threadName.textContent = conversation.other_name;
        threadAbout.textContent = aboutText(conversation);
        threadStoreLink.href = `/storefronts/${conversation.storefront_id}`;
        threadStoreLink.hidden = conversation.role === "seller";
        threadMessages.textContent = "";

        threadPlaceholder.hidden = true;
        threadInner.hidden = false;
        page.classList.add("thread-open");
        setUrlConversation(conversation.id);

        const { messages } = await api(`/api/conversations/${conversation.id}/messages`);
        if (!messages.length) {
            const starter = conversation.role === "buyer"
                ? `Say hi to ${conversation.other_name}! Ask about sizing, availability, or where to meet for pickup.`
                : "No messages yet.";
            threadMessages.append(el("p", "thread-empty", starter));
        }
        appendMessages(messages);
        renderInbox();
        loadInbox();
        composerInput.focus();
    } catch (error) {
        console.error("Could not open conversation:", error);
        state.active = null;
        threadInner.hidden = true;
        threadPlaceholder.hidden = false;
        threadPlaceholder.textContent = error.status === 404 ? "Conversation not found." : "Could not load this conversation.";
        setUrlConversation(null);
    } finally {
        state.loadingThread = false;
    }
}

function closeConversationOnPhone() {
    page.classList.remove("thread-open");
}

async function pollThread() {
    if (!state.active || document.hidden || state.loadingThread) return;
    try {
        const { messages } = await api(`/api/conversations/${state.active.id}/messages?after=${state.lastMessageId}`);
        appendMessages(messages);
    } catch (error) {
        console.error("Could not check for new messages:", error);
    }
}


// sending

async function sendMessage(event) {
    event.preventDefault();
    if (!state.active) return;

    const body = composerInput.value.trim();
    if (!body) return;

    composerSend.disabled = true;
    composerError.textContent = "";
    try {
        const { message } = await api(`/api/conversations/${state.active.id}/messages`, {
            method: "POST",
            body: JSON.stringify({ body }),
        });
        composerInput.value = "";
        resizeComposer();
        threadMessages.scrollTop = threadMessages.scrollHeight;
        appendMessages([message]);
        threadMessages.scrollTop = threadMessages.scrollHeight;
        loadInbox();
    } catch (error) {
        composerError.textContent = error.message;
    } finally {
        composerSend.disabled = false;
        composerInput.focus();
    }
}

function resizeComposer() {
    composerInput.style.height = "auto";
    composerInput.style.height = `${composerInput.scrollHeight}px`;
}


// start

composer.addEventListener("submit", sendMessage);
composerInput.addEventListener("input", resizeComposer);
composerInput.addEventListener("keydown", (event) => {
    // Enter sends, Shift+Enter adds a new line
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        composer.requestSubmit();
    }
});
threadBack.addEventListener("click", closeConversationOnPhone);

setInterval(pollThread, THREAD_POLL_MS);
setInterval(() => { if (!document.hidden) loadInbox(); }, INBOX_POLL_MS);
document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
        pollThread();
        loadInbox();
    }
});

(async function init() {
    await loadInbox();
    const requestedId = Number(new URLSearchParams(window.location.search).get("c"));
    if (requestedId) {
        openConversation(requestedId);
    } else if (state.conversations.length && window.matchMedia("(min-width: 761px)").matches) {
        openConversation(state.conversations[0].id);
    }
})();
