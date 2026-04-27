// ══════════════════════════════════════════════
// Chart.js — Statistics Dashboard
// ══════════════════════════════════════════════

const chartColors = {
    primary: '#ff2800',  // Rosso Corsa
    safe: '#00cc66',     // Bright Green
    warning: '#ffcc00',  // Giallo Modena
    danger: '#ff2800',   // Rosso Corsa
    info: '#ffffff',     // Crisp White
    gridColor: 'rgba(255, 255, 255, 0.1)',
    textColor: '#a0a0a0',
};

Chart.defaults.color = chartColors.textColor;
Chart.defaults.borderColor = chartColors.gridColor;
Chart.defaults.animation = {
    duration: 500, // Thần tốc
    easing: 'easeOutQuart'
};

let dailyChart = null;
let topDriversChart = null;
let heatmapChart = null;

async function loadStatistics() {
    try {
        const resp = await fetch('/api/statistics/summary');
        if (!resp.ok) return;
        const data = await resp.json();

        // KPI Cards
        document.getElementById('kpi-alerts').textContent = data.kpi.total_alerts_week;
        document.getElementById('kpi-sessions').textContent = data.kpi.total_sessions_week;
        document.getElementById('kpi-hours').textContent = data.kpi.total_driving_hours + 'h';
        document.getElementById('kpi-avg').textContent = data.kpi.avg_session_hours + 'h';

        renderDailyChart(data.daily_alerts);
        renderTopDriversChart(data.top_drivers);
        renderHeatmapChart(data.hourly_heatmap);
    } catch (err) {
        console.error('Failed to load statistics:', err);
    }
}

function renderDailyChart(dailyData) {
    const ctx = document.getElementById('dailyChart');
    if (!ctx) return;

    const labels = Object.keys(dailyData).sort();
    const values = labels.map(d => dailyData[d]);

    if (dailyChart) dailyChart.destroy();
    dailyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.map(d => {
                const parts = d.split('-');
                return `${parts[2]}/${parts[1]}`;
            }),
            datasets: [{
                label: 'Số cảnh báo',
                data: values,
                backgroundColor: values.map(v =>
                    v > 10 ? chartColors.danger :
                        v > 5 ? chartColors.warning :
                            chartColors.info
                ),
                borderRadius: 4,
                borderSkipped: false,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 },
                    grid: { color: chartColors.gridColor },
                },
                x: {
                    grid: { display: false },
                },
            },
        },
    });
}

function renderTopDriversChart(topDrivers) {
    const ctx = document.getElementById('topDriversChart');
    if (!ctx) return;

    if (!topDrivers.length) {
        ctx.parentElement.innerHTML = '<p style="text-align:center;color:#8b949e;padding:40px;">Chưa có dữ liệu tài xế</p>';
        return;
    }

    const labels = topDrivers.map(d => d.name);
    const values = topDrivers.map(d => d.count);

    if (topDriversChart) topDriversChart.destroy();
    topDriversChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Số lần cảnh báo',
                data: values,
                backgroundColor: [
                    chartColors.danger,
                    chartColors.warning,
                    chartColors.info,
                    chartColors.safe,
                    chartColors.primary,
                ],
                borderRadius: 4,
                borderSkipped: false,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { precision: 0 },
                    grid: { color: chartColors.gridColor },
                },
                y: {
                    grid: { display: false },
                },
            },
        },
    });
}

function renderHeatmapChart(heatmapData) {
    const ctx = document.getElementById('heatmapChart');
    if (!ctx) return;

    // Build matrix data
    const days = new Set();
    const hours = Array.from({ length: 24 }, (_, i) => i);

    Object.keys(heatmapData).forEach(key => {
        const [day] = key.split('_');
        days.add(day);
    });

    const sortedDays = Array.from(days).sort();

    if (!sortedDays.length) {
        ctx.parentElement.innerHTML = '<p style="text-align:center;color:#8b949e;padding:40px;">Chưa có dữ liệu để tạo heatmap</p>';
        return;
    }

    // Use bubble chart as heatmap proxy
    const datasets = [];
    sortedDays.forEach((day, dayIdx) => {
        hours.forEach(hour => {
            const key = `${day}_${hour}`;
            const count = heatmapData[key] || 0;
            if (count > 0) {
                datasets.push({ x: hour, y: dayIdx, r: Math.min(count * 3, 20), count });
            }
        });
    });

    if (heatmapChart) heatmapChart.destroy();
    heatmapChart = new Chart(ctx, {
        type: 'bubble',
        data: {
            datasets: [{
                label: 'Mật độ cảnh báo',
                data: datasets,
                backgroundColor: datasets.map(d =>
                    d.count > 5 ? 'rgba(248,81,73,0.6)' :
                        d.count > 2 ? 'rgba(210,153,34,0.6)' :
                            'rgba(56,139,253,0.4)'
                ),
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            return `${ctx.raw.count} cảnh báo`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    min: -0.5,
                    max: 23.5,
                    ticks: {
                        callback: v => `${v}h`,
                        stepSize: 1,
                    },
                    title: { display: true, text: 'Giờ trong ngày' },
                    grid: { color: chartColors.gridColor },
                },
                y: {
                    min: -0.5,
                    max: sortedDays.length - 0.5,
                    ticks: {
                        callback: (v) => {
                            const day = sortedDays[v];
                            if (!day) return '';
                            const parts = day.split('-');
                            return `${parts[2]}/${parts[1]}`;
                        },
                        stepSize: 1,
                    },
                    title: { display: true, text: 'Ngày' },
                    grid: { color: chartColors.gridColor },
                },
            },
        },
    });
}
