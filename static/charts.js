// 仪表盘图表：数据从 <script type="application/json"> 注入，
// Chart.js 由本地 static/vendor 提供（无外部 CDN，兼容 CSP self）
(function () {
    const dataEl = document.getElementById("chart-data");
    if (!dataEl || typeof Chart === "undefined") return;
    const data = JSON.parse(dataEl.textContent);
    const palette = [
        "#167a5a", "#3f9d7b", "#e0a458", "#5b8dbf", "#b96a7a",
        "#8a80c9", "#74b89c", "#a5a58d", "#c98a5b",
    ];
    const yuan = (value) => "¥ " + Number(value).toLocaleString("zh-CN", {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
    });

    const trendEl = document.getElementById("trend-chart");
    if (trendEl && data.monthly.length) {
        new Chart(trendEl, {
            type: "line",
            data: {
                labels: data.monthly.map((row) => row.month),
                datasets: [{
                    label: "月支出",
                    data: data.monthly.map((row) => row.value),
                    borderColor: "#167a5a",
                    backgroundColor: "rgba(22, 122, 90, .12)",
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    pointBackgroundColor: "#167a5a",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => yuan(c.parsed.y) } },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: (v) => "¥" + Number(v).toLocaleString("zh-CN"),
                        },
                    },
                },
            },
        });
    }

    const categoryEl = document.getElementById("category-chart");
    if (categoryEl && data.categories.length) {
        new Chart(categoryEl, {
            type: "doughnut",
            data: {
                labels: data.categories.map((row) => row.label),
                datasets: [{
                    data: data.categories.map((row) => row.value),
                    backgroundColor: palette.slice(0, data.categories.length),
                    borderWidth: 2,
                    borderColor: "#ffffff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { boxWidth: 12, padding: 14 },
                    },
                    tooltip: {
                        callbacks: {
                            label: (c) => c.label + " " + yuan(c.parsed),
                        },
                    },
                },
            },
        });
    }
})();
