const chatPanel = document.getElementById("chatPanel");
const chatToggle = document.getElementById("chatToggle");
const chatClose = document.getElementById("chatClose");

chatToggle.addEventListener("click", () => {
    chatPanel.classList.add("open");
});

chatClose.addEventListener("click", () => {
    chatPanel.classList.remove("open");
});