(function () {
    const MOBILE_QUERY = '(max-width: 768px)';
    const mobileMedia = window.matchMedia(MOBILE_QUERY);

    function setWebViewHeight() {
        document.documentElement.style.setProperty('--webview-vh', `${window.innerHeight * 0.01}px`);
    }

    function setMobileTitle() {
        const titleTarget = document.getElementById('mobile-page-title');
        if (!titleTarget || !document.body) return;
        const title = document.body.dataset.mobileTitle || document.title.split('-')[0].trim() || 'WebQuanLi';
        titleTarget.textContent = title;
    }

    function syncConnectionPill() {
        const pill = document.getElementById('mobile-connection-pill');
        if (!pill) return;

        const connection = document.getElementById('connection-status');
        const textNode = pill.querySelector('span:last-child');
        const dot = pill.querySelector('.status-dot');

        if (!connection) {
            if (textNode) textNode.textContent = 'WebView';
            if (dot) {
                dot.classList.remove('offline');
                dot.classList.add('online');
            }
            pill.classList.remove('is-offline');
            return;
        }

        const state = connection.dataset.connectionState || '';
        const label = connection.querySelector('.connection-text')?.textContent?.trim()
            || (state === 'online' ? 'Kết nối' : 'Mất kết nối');
        if (textNode) textNode.textContent = label;
        if (dot) {
            dot.classList.toggle('online', state === 'online');
            dot.classList.toggle('offline', state !== 'online');
        }
        pill.classList.toggle('is-offline', state !== 'online');
    }

    function syncFilterDrawers(isMobile) {
        document.querySelectorAll('.mobile-filter-drawer').forEach((drawer) => {
            if (isMobile) {
                if (!drawer.dataset.mobileInitialized) {
                    drawer.open = false;
                    drawer.dataset.mobileInitialized = 'true';
                }
                return;
            }
            drawer.open = true;
        });
    }

    function applyMobileMode() {
        const isMobile = mobileMedia.matches;
        document.body?.classList.toggle('mobile-webview-mode', isMobile);
        syncFilterDrawers(isMobile);
        syncConnectionPill();
    }

    function bootMobileWebView() {
        setWebViewHeight();
        setMobileTitle();
        applyMobileMode();
    }

    window.addEventListener('resize', () => {
        setWebViewHeight();
        applyMobileMode();
    }, { passive: true });

    window.addEventListener('orientationchange', () => {
        window.setTimeout(() => {
            setWebViewHeight();
            applyMobileMode();
        }, 120);
    }, { passive: true });

    document.addEventListener('DOMContentLoaded', bootMobileWebView);
    document.addEventListener('htmx:afterSwap', applyMobileMode);
    window.DrowsiGuardMobileWebView = {
        applyMobileMode,
        setWebViewHeight,
        syncConnectionPill,
    };
})();
