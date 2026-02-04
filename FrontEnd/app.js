const CATEGORIES = [
  "restaurant",
  "groceries",
  "cafe_beverages",
  "transport",
  "shopping",
  "utilities",
  "health",
  "education",
  "entertainment",
  "electronics",
  "household",
  "travel",
  "finance",
  "gifts_donations",
  "other"
];


const imageInput = document.getElementById("imageInput");
const previewGrid = document.getElementById("previewGrid");
const processBtn = document.getElementById("processBtn");

const loadingOverlay = document.getElementById("loadingOverlay");
const loadingText = document.getElementById("loadingText");

const resultSection = document.getElementById("resultSection");
const vendorName = document.getElementById("vendorName");
const vendorAddress = document.getElementById("vendorAddress");
const vendorPhone = document.getElementById("vendorPhone");
const docDate = document.getElementById("docDate");
const docTime = document.getElementById("docTime");
const totalAmount = document.getElementById("totalAmount");

const itemsBody = document.getElementById("itemsBody");

const steps = [
  "Uploading image…",
  "OCR in progress…",
  "Understanding document structure…",
  "Extracting items & totals…",
  "Almost done…"
];

let stepIndex = 0;
let stepInterval = null;
const loadingStep = document.getElementById("loadingStep");

const imagePreview = document.getElementById("imagePreview");

imageInput.addEventListener("change", () => {
  imagePreview.innerHTML = "";
  resultSection.classList.add("hidden");

  const file = imageInput.files[0];
  if (!file) {
    processBtn.disabled = true;
    return;
  }

  const reader = new FileReader();
  reader.onload = e => {
    const img = document.createElement("img");
    img.src = e.target.result;
    imagePreview.appendChild(img);
  };
  reader.readAsDataURL(file);

  processBtn.disabled = false;
});
/* -------- PROCESS -------- */
processBtn.addEventListener("click", async () => {
  const file = imageInput.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("image", file); // 🔑 backend expects this

  processBtn.disabled = true;
  processBtn.textContent = "Processing...";
  showLoading(); // ✅ START shimmer

  try {
    const res = await fetch("http://localhost:5000/predict", {
      method: "POST",
      body: formData
    });

    if (!res.ok) throw new Error("Server error");

    const data = await res.json();

    console.log(data);

    hideLoading(); // ✅ STOP shimmer
    populateResult(data.parsed_output); // ✅ NOW populate UI

  } catch (err) {
    hideLoading(); // ✅ STOP shimmer even on error
    alert("Failed to process document");
    console.error(err);
  }

  processBtn.textContent = "Process Document";
  processBtn.disabled = false;
});


/* -------- LOADING UI -------- */
function showLoading() {
  loadingOverlay.classList.remove("hidden");
  loadingText.textContent = "Keep calm, your document is processing…";

  stepIndex = 0;
  loadingStep.textContent = steps[stepIndex];

  stepInterval = setInterval(() => {
    stepIndex = (stepIndex + 1) % steps.length;
    loadingStep.textContent = steps[stepIndex];
  }, 2500);
}


function hideLoading() {
  loadingOverlay.classList.add("hidden");

  if (stepInterval) {
    clearInterval(stepInterval);
    stepInterval = null;
  }

  loadingStep.textContent = "";
}


function showSaveLoading() {
  loadingOverlay.classList.remove("hidden");
  loadingText.textContent = "Saving receipt…";
}

function hideSaveLoading() {
  loadingOverlay.classList.add("hidden");
}

function createItemRow(item = {}) {
  const row = document.createElement("div");
  row.className = "item-row";

  const categoryOptions = CATEGORIES
    .map(c => `<option ${c === item.category ? "selected" : ""}>${c}</option>`)
    .join("");

  row.innerHTML = `
    <input value="${item.name ?? ""}" placeholder="Item name" />
    <input type="number" value="${item.quantity ?? 1}" />
    <input type="number" step="0.01" value="${item.price ?? ""}" />
    <select>${categoryOptions}</select>
    <button class="delete-item" title="Remove item">✕</button>
  `;

  row.querySelector(".delete-item").addEventListener("click", () => {
    row.remove();
  });

  return row;
}


/* -------- POPULATE RESULT -------- */
function populateResult(output) {
  resultSection.classList.remove("hidden");

  vendorName.value = output.vendor_name ?? "";
  vendorAddress.value = output.vendor_address ?? "";
  vendorPhone.value = output.vendor_phone ?? "";

  docDate.value = output.date ?? "";
  docTime.value = output.time ?? "";

  totalAmount.value = output.total_amount ?? "";

  itemsBody.innerHTML = "";

  output.items.forEach(item => {
    itemsBody.appendChild(createItemRow(item));
  });
}

document.getElementById("addItemBtn").addEventListener("click", () => {
  itemsBody.appendChild(createItemRow());
});


document.getElementById("saveBtn").addEventListener("click", async () => {
  const items = [...itemsBody.children].map(row => {
    const fields = row.querySelectorAll("input, select");
    return {
      name: fields[0].value,
      quantity: Number(fields[1].value),
      price: Number(fields[2].value),
      category: fields[3].value
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

  console.log("SAVE PAYLOAD:", payload);

  try {
    showSaveLoading();
    const res = await fetch("http://localhost:5000/store-receipt", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error("Server error");
    }

    const data = await res.json();

    if (data.status === "ok") {
      showToast("Saved successfully ✅");
      resetUI();
    } else {
      showToast("Save failed ❌");
    }

  } catch (err) {
    console.error("Save error:", err);
    alert("❌ Unable to save receipt");
  }finally {
    // 🔄 STOP loading (always)
    hideSaveLoading();
  }
});

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.remove("hidden");
  toast.classList.add("show");

  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.classList.add("hidden"), 300);
  }, 2000);
}

function resetUI() {
  // hide result section
  resultSection.classList.add("hidden");

  // clear preview image
  imagePreview.innerHTML = "";

  // reset file input
  imageInput.value = "";

  // // clear items
  // itemsBody.innerHTML = "";

  // // reset fields
  // vendorName.value = "";
  // vendorAddress.value = "";
  // vendorPhone.value = "";
  // docDate.value = "";
  // docTime.value = "";
  // totalAmount.value = "";

  processBtn.disabled = true;
}
