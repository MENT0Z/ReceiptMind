const API = "http://localhost:5000";

const imageInput = document.getElementById("imageInput");
const imagePreview = document.getElementById("imagePreview");
const processBtn = document.getElementById("processBtn");
const pendingList = document.getElementById("pendingList");

const resultSection = document.getElementById("resultSection");

const vendorName = document.getElementById("vendorName");
const vendorAddress = document.getElementById("vendorAddress");
const vendorPhone = document.getElementById("vendorPhone");
const docDate = document.getElementById("docDate");
const docTime = document.getElementById("docTime");
const totalAmount = document.getElementById("totalAmount");
const itemsBody = document.getElementById("itemsBody");

const toast = document.getElementById("toast");

let activeId = null;

const DB_NAME = "ReceiptBGDB";
const STORE_NAME = "pendingReceipts";
const DB_VERSION = 1;

function openDB() {
    return new Promise((resolve, reject) => {

        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = function(e) {
            const db = e.target.result;

            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, {
                    keyPath: "id"
                });
            }
        };

        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);

    });
}

/* =========================
   STORAGE
========================= */

// function getReceipts() {
//     return JSON.parse(localStorage.getItem("pending_receipts") || "[]");
// }

// function saveReceipts(data) {
//     localStorage.setItem("pending_receipts", JSON.stringify(data));
// }

// function addReceipt(obj) {
//     const arr = getReceipts();
//     arr.unshift(obj);
//     saveReceipts(arr);
// }

// function deleteReceipt(id) {
//     const arr = getReceipts().filter(x => x.id !== id);
//     saveReceipts(arr);
// }

async function getReceipts() {

    const db = await openDB();

    return new Promise((resolve, reject) => {

        const tx = db.transaction(STORE_NAME, "readonly");
        const store = tx.objectStore(STORE_NAME);

        const req = store.getAll();

        req.onsuccess = () => resolve(req.result.reverse());
        req.onerror = () => reject(req.error);

    });
}


async function addReceipt(obj) {

    const db = await openDB();

    return new Promise((resolve, reject) => {

        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);

        store.put(obj);

        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);

    });
}


async function deleteReceipt(id) {

    const db = await openDB();

    return new Promise((resolve, reject) => {

        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);

        store.delete(id);

        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);

    });
}


window.removePending = async function(id){

    if(!confirm("Delete this processed receipt?")) return;

    await deleteReceipt(id);
    renderPending();

    showToast("Receipt removed.");
}

/* =========================
   TOAST
========================= */

function showToast(msg) {
    toast.innerText = msg;
    toast.classList.remove("hidden");

    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3500);
}


/* =========================
   RESET UPLOAD SCREEN
========================= */

function resetUploader() {
    imageInput.value = "";
    imagePreview.innerHTML = "";
    processBtn.disabled = true;
    processBtn.innerText = "Process Receipt";
}


/* =========================
   IMAGE PREVIEW
========================= */

imageInput.addEventListener("change", () => {

    const file = imageInput.files[0];
    imagePreview.innerHTML = "";

    if (!file) {
        processBtn.disabled = true;
        return;
    }

    const reader = new FileReader();

    reader.onload = e => {
        imagePreview.innerHTML = `<img src="${e.target.result}">`;
    };

    reader.readAsDataURL(file);

    processBtn.disabled = false;
});


/* =========================
   PROCESS IN BACKGROUND
========================= */

processBtn.addEventListener("click", () => {

    const file = imageInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("image", file);

    const preview = imagePreview.querySelector("img")?.src || "";

    processBtn.disabled = true;
    processBtn.innerText = "Queued...";

    /* instantly reset UI */
    resetUploader();

    showToast("Your image is being processed in background. You can upload more receipts.");

    /* background request continues */
    fetch(`${API}/predict`, {
        method: "POST",
        body: formData
    })
    .then(res => res.json())
    .then(async data => {

    const receipt = {
        id: Date.now() + Math.floor(Math.random()*1000),
        preview: preview,
        parsed_output: data.parsed_output
    };

    await addReceipt(receipt);
    await renderPending();

    showToast("Receipt processed successfully.");

})
    .catch(err => {
        console.error(err);
        showToast("Processing failed.");
    });

});


/* =========================
   PENDING LIST
========================= */

async function renderPending() {

    const arr = await getReceipts();

    pendingList.innerHTML = "";

    if (arr.length === 0) {
        pendingList.innerHTML = "<p>No processed receipts pending.</p>";
        return;
    }

    arr.forEach(item => {

        const div = document.createElement("div");
        div.className = "pending-card";

        div.innerHTML = `
        <div class="pending-left">
            <img src="${item.preview}">
            <div>
                <strong>Receipt #${item.id}</strong><br>
                <span class="badge done">Processed</span>
            </div>
        </div>

        <div class="pending-actions">
    <button onclick="openReceipt(${item.id})">Open</button>
    <button class="delete-btn" onclick="removePending(${item.id})">Delete</button>
</div>
        `;

        pendingList.appendChild(div);
    });
}


/* =========================
   OPEN RECEIPT
========================= */

window.openReceipt = async function(id) {

    const arr = await getReceipts();
    const receipt = arr.find(x => x.id === id);

    if (!receipt) return;

    activeId = id;

    populateForm(receipt.parsed_output);

    resultSection.classList.remove("hidden");

    window.scrollTo({
        top: document.body.scrollHeight,
        behavior: "smooth"
    });
}


/* =========================
   POPULATE FORM
========================= */

function populateForm(data) {

    vendorName.value = data.vendor_name || "";
    vendorAddress.value = data.vendor_address || "";
    vendorPhone.value = data.vendor_phone || "";
    docDate.value = data.date || "";
    docTime.value = data.time || "";
    totalAmount.value = data.total_amount || "";

    itemsBody.innerHTML = "";

    (data.items || []).forEach(item => {
        itemsBody.appendChild(createItemRow(item));
    });
}


/* =========================
   ITEM ROW
========================= */

function createItemRow(item = {}) {

    const row = document.createElement("div");
    row.className = "item-row";

    row.innerHTML = `
        <input value="${item.name || ""}">
        <input type="number" value="${item.quantity || 1}">
        <input type="number" value="${item.price || 0}">
        <button>X</button>
    `;

    row.querySelector("button").onclick = () => row.remove();

    return row;
}

document.getElementById("addItemBtn").onclick = () => {
    itemsBody.appendChild(createItemRow());
};


/* =========================
   SAVE
========================= */

document.getElementById("saveBtn").addEventListener("click", async () => {

    const items = [...itemsBody.children].map(row => {

        const i = row.querySelectorAll("input");

        return {
            name: i[0].value,
            quantity: Number(i[1].value),
            price: Number(i[2].value)
        };
    });

    const payload = {
        parsed_output: {
            vendor_name: vendorName.value,
            vendor_address: vendorAddress.value,
            vendor_phone: vendorPhone.value,
            date: docDate.value,
            time: docTime.value,
            total_amount: Number(totalAmount.value),
            items
        }
    };

    try {

        const res = await fetch(`${API}/store-receipt`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (data.status === "ok") {

            await deleteReceipt(activeId);
            renderPending();

            resultSection.classList.add("hidden");

            showToast("Saved successfully.");
        }

    } catch (err) {
        showToast("Save failed.");
    }

});


renderPending();