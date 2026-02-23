const API_URL = "http://localhost:5000/chat";

const messagesDiv = document.getElementById("messages");
const input = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");

/* =========================
   BASIC MESSAGE
========================= */
function addMessage(text, className) {
    const msg = document.createElement("div");
    msg.className = `message ${className}`;
    msg.innerText = text;
    messagesDiv.appendChild(msg);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

/* =========================
   AGENT MESSAGE (EXPANDABLE)
========================= */
function addAgentMessage(mainData, fullData) {
    const wrapper = document.createElement("div");
    wrapper.className = "message agent";

    let resultText = "No results found.";

    if (mainData?.results && Array.isArray(mainData.results)) {
        resultText = mainData.results
            .map(row =>
                Object.entries(row)
                    .map(([k, v]) => `${k}: ${v}`)
                    .join(", ")
            )
            .join("\n");
    }

    const content = document.createElement("div");
    content.innerText = resultText;

    const toggle = document.createElement("div");
    toggle.className = "expand-toggle";
    toggle.innerText = "▾ More";

    const expanded = document.createElement("pre");
    expanded.className = "json-view";
    expanded.innerText = JSON.stringify(fullData, null, 2);
    expanded.style.display = "none";

    toggle.addEventListener("click", () => {
        const isOpen = expanded.style.display === "block";
        expanded.style.display = isOpen ? "none" : "block";
        toggle.innerText = isOpen ? "▾ More" : "▴ Less";
    });

    wrapper.appendChild(content);
    wrapper.appendChild(toggle);
    wrapper.appendChild(expanded);

    messagesDiv.appendChild(wrapper);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

/* =========================
   TYPING INDICATOR
========================= */
function showTyping() {
    const typing = document.createElement("div");
    typing.className = "typing";
    typing.id = "typingIndicator";

    typing.innerHTML = `
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
    `;

    messagesDiv.appendChild(typing);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function removeTyping() {
    const typing = document.getElementById("typingIndicator");
    if (typing) typing.remove();
}

/* =========================
   SEND MESSAGE
========================= */
async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    addMessage(text, "user");
    input.value = "";
    sendBtn.disabled = true;

    showTyping();

    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();
        removeTyping();

        if (data.success) {
            addAgentMessage(data.response, data);
        } else {
            addMessage("Error: " + (data.error || "Unknown error"), "agent");
        }

    } catch (error) {
        removeTyping();
        addMessage("Error connecting to backend.", "agent");
    }

    sendBtn.disabled = false;
}

/* =========================
   EVENTS
========================= */
sendBtn.addEventListener("click", sendMessage);

input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        sendMessage();
    }
});