function ensureToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'true');
        document.body.appendChild(container);
    }
    return container;
}

function showToast(message, type = 'info', timeoutMs = 3200) {
    const container = ensureToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', type === 'error' ? 'alert' : 'status');
    toast.textContent = message || 'Đã cập nhật';
    container.appendChild(toast);

    window.setTimeout(() => {
        toast.classList.add('toast-exit');
        window.setTimeout(() => toast.remove(), 180);
    }, timeoutMs);
}

async function apiErrorMessage(response, fallback = 'Không thể xử lý yêu cầu') {
    try {
        const payload = await response.json();
        return payload.detail || fallback;
    } catch (error) {
        return fallback;
    }
}
