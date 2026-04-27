// ══════════════════════════════════════════════
// Session Timer — Live driving time counter
// ══════════════════════════════════════════════

let sessionInterval = null;

function initSessionTimer() {
    if (sessionInterval) clearInterval(sessionInterval);

    const timerEl = document.querySelector('.session-timer');
    if (!timerEl) return;

    const checkinStr = timerEl.dataset.checkin;
    if (!checkinStr) return;

    const checkinTime = new Date(checkinStr);

    function updateTimer() {
        if (timerEl.dataset.stopped === 'true') {
            clearInterval(sessionInterval);
            return;
        }

        const now = new Date();
        const diff = Math.floor((now - checkinTime) / 1000);

        if (diff < 0) return;

        const hours = Math.floor(diff / 3600);
        const mins = Math.floor((diff % 3600) / 60);
        const secs = diff % 60;

        const pad = n => n.toString().padStart(2, '0');
        timerEl.textContent = `⏳ Thời gian lái: ${pad(hours)}:${pad(mins)}:${pad(secs)}`;
    }

    updateTimer();
    sessionInterval = setInterval(updateTimer, 1000);
}

// Auto-init when DOM is ready
document.addEventListener('DOMContentLoaded', initSessionTimer);
