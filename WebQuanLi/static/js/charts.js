const chartColors = {
    primary: '#0f766e',
    safe: '#16a34a',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#0284c7',
    gridColor: 'rgba(15, 23, 42, 0.10)',
    textColor: '#334155',
};

Chart.defaults.color = chartColors.textColor;
Chart.defaults.borderColor = chartColors.gridColor;
Chart.defaults.animation = {
    duration: 500,
    easing: 'easeOutQuart',
};

let dailyChart = null;
let topDriversChart = null;
let heatmapChart = null;

async function loadStatistics() {
    try {
        const resp = await fetch('/api/statistics/summary');
        if (!resp.ok) return;
        const data = await resp.json();

        document.getElementById('kpi-alerts').textContent = data.kpi.total_alerts_week;
        document.getElementById('kpi-sessions').textContent = data.kpi.total_sessions_week;
        document.getElementById('kpi-hours').textContent = data.kpi.total_driving_hours + 'h';
        document.getElementById('kpi-avg').textContent = data.kpi.avg_session_hours + 'h';

        renderDailyChart(data.daily_alerts || {});
        renderTopDriversChart(data.top_drivers || []);
        renderHeatmapChart(data.hourly_heatmap || {});
        renderDriverViolationTable(data.driver_violation_stats || []);
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
                    v > 10 ? 'rgba(239, 68, 68, 0.78)' :
                        v > 5 ? 'rgba(245, 158, 11, 0.78)' :
                            'rgba(2, 132, 199, 0.74)'
                ),
                borderColor: values.map(v =>
                    v > 10 ? 'rgba(185, 28, 28, 0.72)' :
                        v > 5 ? 'rgba(180, 83, 9, 0.72)' :
                            'rgba(14, 116, 144, 0.70)'
                ),
                borderWidth: 1,
                borderRadius: 10,
                borderSkipped: false,
                barPercentage: 0.62,
                categoryPercentage: 0.72,
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

function moneyVnd(value) {
    return `${Number(value || 0).toLocaleString('vi-VN')}đ`;
}

function shortDateTime(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '-';
    return date.toLocaleString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function renderDriverViolationTable(driverViolationStats) {
    const body = document.getElementById('driver-violation-body');
    if (!body) return;

    if (!driverViolationStats.length) {
        body.innerHTML = `
            <tr id="driver-violation-empty">
                <td colspan="7" class="text-center text-muted">
                    Chưa có vi phạm buồn ngủ mức 3 trong 7 ngày gần nhất
                </td>
            </tr>
        `;
        return;
    }

    body.innerHTML = driverViolationStats.map(item => {
        const amount = item.active_amount_display || moneyVnd(item.active_amount_vnd);
        return `
            <tr>
                <td data-label="Tài xế"><strong>${item.driver_name || 'N/A'}</strong></td>
                <td data-label="Mức 3">${item.level3_count || 0}</td>
                <td data-label="Chưa xử lý">${item.pending_count || 0}</td>
                <td data-label="Đã xác nhận">${item.confirmed_count || 0}</td>
                <td data-label="Đã hủy">${item.cancelled_count || 0}</td>
                <td data-label="Tiền phạt còn hiệu lực">${amount}</td>
                <td data-label="Lần gần nhất">${shortDateTime(item.last_violation_at)}</td>
            </tr>
        `;
    }).join('');
}

function renderTopDriversChart(topDrivers) {
    const ctx = document.getElementById('topDriversChart');
    if (!ctx) return;

    if (!topDrivers.length) {
        ctx.parentElement.innerHTML = '<p style="text-align:center;color:#64748b;padding:40px;">Chưa có dữ liệu tài xế</p>';
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
                    'rgba(15, 118, 110, 0.82)',
                    'rgba(2, 132, 199, 0.78)',
                    'rgba(245, 158, 11, 0.78)',
                    'rgba(239, 68, 68, 0.74)',
                    'rgba(22, 163, 74, 0.76)',
                ],
                borderColor: 'rgba(255, 255, 255, 0.86)',
                borderWidth: 1,
                borderRadius: 10,
                borderSkipped: false,
                barPercentage: 0.58,
                categoryPercentage: 0.70,
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

    const days = new Set();
    const hours = Array.from({ length: 24 }, (_, i) => i);

    Object.keys(heatmapData).forEach(key => {
        const [day] = key.split('_');
        days.add(day);
    });

    const sortedDays = Array.from(days).sort();

    if (!sortedDays.length) {
        ctx.parentElement.innerHTML = '<p style="text-align:center;color:#64748b;padding:40px;">Chưa có dữ liệu để tạo heatmap</p>';
        return;
    }

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
                    d.count > 5 ? 'rgba(220, 38, 38, 0.60)' :
                        d.count > 2 ? 'rgba(217, 119, 6, 0.60)' :
                            'rgba(37, 99, 235, 0.40)'
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
