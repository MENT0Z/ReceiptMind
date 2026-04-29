// async function initDashboard() {
//     try {
//         const response = await fetch('http://localhost:5000/dashboard-stats');
//         const result = await response.json();
//         const data = result.data;

//         // 1. Update Stats
//         document.getElementById('totalSpent').innerText = `$${data.total_spent.toLocaleString()}`;
//         document.getElementById('totalReceipts').innerText = data.total_receipts;
//         document.getElementById('avgReceipt').innerText = `$${data.avg_spent_per_receipt.toFixed(2)}`;

//         const topCat = data.top_categories[0];
//         document.getElementById('topCategoryName').innerText = topCat.category_name;
//         const percent = ((topCat.total_spent / data.total_spent) * 100).toFixed(0);
//         document.getElementById('topCategoryPercent').innerText = `${percent}% of spend`;

//         // 2. Line Chart (Yearly Spending)
//         const ctxLine = document.getElementById('lineChart').getContext('2d');
//         new Chart(ctxLine, {
//             type: 'line',
//             data: {
//                 labels: data.yearly_spending.map(y => y.year),
//                 datasets: [{
//                     label: 'Spending',
//                     data: data.yearly_spending.map(y => y.total_spent),
//                     borderColor: '#2563eb',
//                     fill: true,
//                     backgroundColor: 'rgba(37, 99, 235, 0.1)',
//                     tension: 0.4
//                 }]
//             },
//             options: { maintainAspectRatio: false, plugins: { legend: { display: false } } }
//         });

//         // 3. Category Doughnut Chart
//         const ctxDonut = document.getElementById('categoryChart').getContext('2d');
//         const categories = data.top_categories.slice(0, 5);

//         new Chart(ctxDonut, {
//             type: 'doughnut',
//             data: {
//                 labels: categories.map(c => c.category_name),
//                 datasets: [{
//                     data: categories.map(c => c.total_spent),
//                     backgroundColor: ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#94a3b8']
//                 }]
//             },
//             options: { plugins: { legend: { display: false } } }
//         });

//         // 4. Fill Category Legend & Table
//         const list = document.getElementById('categoryList');
//         categories.forEach(c => {
//             list.innerHTML += `<li><span>${c.category_name}</span> <strong>$${c.total_spent}</strong></li>`;
//         });

//         const tableBody = document.getElementById("receiptsTable");
//         tableBody.innerHTML = "";

//         data.recent_receipts.forEach((r, index) => {
//             const date = r.receipt_datetime
//                 ? new Date(r.receipt_datetime).toLocaleDateString()
//                 : "—";

//             tableBody.innerHTML += `
//         <tr>
//             <td>Receipt ${index + 1}</td>
//             <td>${date}</td>
//             <td>$${r.total}</td>
//         </tr>
//     `;
//         });

//     } catch (error) {
//         console.error("Error loading dashboard data:", error);
//     }
// }
async function initDashboard() {
    try {
        const response = await fetch('http://localhost:5000/dashboard-stats');
        const result = await response.json();
        const data = result.data;

        /* ------------------ 1. STATS ------------------ */
        // document.getElementById('totalSpent').innerText =
        //     `$${data.total_spent.toLocaleString()}`;

        document.getElementById('totalReceipts').innerText =
            data.total_receipts;

        document.getElementById('avgReceipt').innerText =
            `$${data.avg_spent_per_receipt.toFixed(2)}`;

        /* ---- Top Category (OPTIONAL) ---- */
        const topName = document.getElementById('topCategoryName');
        const topPercent = document.getElementById('topCategoryPercent');

        if (topName && topPercent && data.top_categories?.length) {
            const topCat = data.top_categories[0];
            const percent =
                ((topCat.total_spent / data.total_spent) * 100).toFixed(0);

            topName.innerText = topCat.category_name;
            topPercent.innerText = `${percent}% of spend`;
        }

        /* ------------------ 2. LINE CHART ------------------ */
        const lineCanvas = document.getElementById('lineChart');

        if (lineCanvas && data.yearly_spending?.length) {
            const ctxLine = lineCanvas.getContext('2d');

            new Chart(ctxLine, {
                type: 'line',
                data: {
                    labels: data.yearly_spending.map(y => y.year),
                    datasets: [{
                        label: 'Spending',
                        data: data.yearly_spending.map(y => y.total_spent),
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } }
                }
            });
        }

        /* ------------------ 3. CATEGORY CHART (OPTIONAL) ------------------ */
        const donutCanvas = document.getElementById('categoryChart');
        const categoryList = document.getElementById('categoryList');

        if (donutCanvas && categoryList && data.top_categories?.length) {
            const categories = data.top_categories.slice(0, 5);

            new Chart(donutCanvas.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: categories.map(c => c.category_name),
                    datasets: [{
                        data: categories.map(c => c.total_spent),
                        backgroundColor: [
                            '#2563eb', '#10b981', '#f59e0b',
                            '#8b5cf6', '#94a3b8'
                        ]
                    }]
                },
                options: {
                    plugins: { legend: { display: false } }
                }
            });

            categoryList.innerHTML = "";
            categories.forEach(c => {
                categoryList.innerHTML += `
                    <li>
                        <span>${c.category_name}</span>
                        <strong>$${c.total_spent}</strong>
                    </li>`;
            });
        }

        /* ------------------ 4. RECENT RECEIPTS TABLE ------------------ */
        const tableBody = document.getElementById("receiptsTable");

        if (tableBody && data.recent_receipts?.length) {
            tableBody.innerHTML = "";

            data.recent_receipts.forEach((r, index) => {
                const date = r.receipt_datetime
                    ? new Date(r.receipt_datetime).toLocaleDateString()
                    : "—";

                tableBody.innerHTML += `
                    <tr>
                        <td>Receipt ${index + 1}</td>
                        <td>${date}</td>
                        <td>$${r.total}</td>
                    </tr>
                `;
            });
        }

    } catch (error) {
        console.error("Error loading dashboard data:", error);
    }
}
async function openReceiptsDrawer() {
    const res = await fetch("http://localhost:5000/receipts");
    const json = await res.json();

    const container = document.getElementById("receiptsList");
    container.innerHTML = "";

    json.data.forEach((r, index) => {

        const title =
            r.vendor_name ||
            r.vendor_address ||
            (r.receipt_datetime
                ? new Date(r.receipt_datetime).toLocaleDateString()
                : `Receipt ${index + 1}`);

        const subtitle =
            r.vendor_address ||
            (r.receipt_datetime
                ? new Date(r.receipt_datetime).toLocaleString()
                : "");

        const card = document.createElement("div");
        card.className = "receipt-card";

        card.innerHTML = `
            <div class="receipt-header">
                <div>
                    <div>${title}</div>
                    <small style="color:#64748b">${subtitle}</small>
                </div>
                <div>$${r.total}</div>
            </div>

            <div class="receipt-items">
                ${r.items.map(i => `
                    <div class="item-row">
                        <span>${i.name} × ${i.quantity}</span>
                        <span>$${i.total_price}</span>
                    </div>
                `).join("")}
            </div>
        `;

        card.onclick = () => {
            card.querySelector(".receipt-items")
                .classList.toggle("open");
        };

        container.appendChild(card);
    });

    document.getElementById("receiptsDrawer").classList.add("open");
}

function closeReceiptsDrawer() {
    document.getElementById("receiptsDrawer").classList.remove("open");
}

initDashboard();