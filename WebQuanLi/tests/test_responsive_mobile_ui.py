from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = PROJECT_ROOT / "templates"
STYLE_CSS = PROJECT_ROOT / "static" / "css" / "style.css"
CHARTS_JS = PROJECT_ROOT / "static" / "js" / "charts.js"
MOBILE_WEBVIEW_JS = PROJECT_ROOT / "static" / "js" / "mobile_webview.js"
MOBILE_TOKEN = "mobile-webview-20260607"


def read_template(name: str) -> str:
    return TEMPLATES.joinpath(name).read_text(encoding="utf-8")


def test_base_shell_exposes_mobile_navigation_contract():
    html = read_template("base.html")

    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in html
    assert f'/static/css/style.css?v={MOBILE_TOKEN}' in html
    for nav_id in ["nav-dashboard", "nav-history", "nav-fleet", "nav-penalties", "nav-statistics", "nav-logout"]:
        assert f'id="{nav_id}"' in html
    for icon in ["🚗", "📊", "📋", "🚛", "⚠️", "📈", "👤", "🚪"]:
        assert icon in html
    assert "/settings" not in html


def test_login_page_uses_versioned_css_for_webview_cache_busting():
    html = read_template("login.html")

    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in html
    assert f'/static/css/style.css?v={MOBILE_TOKEN}' in html


def test_core_templates_do_not_render_mojibake_markers():
    template_paths = [
        TEMPLATES / "base.html",
        TEMPLATES / "fleet.html",
        TEMPLATES / "penalties.html",
        TEMPLATES / "statistics.html",
        PROJECT_ROOT / "static" / "js" / "charts.js",
    ]
    forbidden = [
        "\u00c3",
        "\u00e1\u00ba",
        "\u00e1\u00bb",
        "\u00c4",
        "\u00c6",
        "\u00f0\u0178",
    ]
    for path in template_paths:
        text = path.read_text(encoding="utf-8")
        found = [marker for marker in forbidden if marker in text]
        assert found == [], f"{path} contains mojibake markers: {found}"


def test_mobile_table_rows_expose_labels_for_card_layout():
    dashboard_alerts = read_template("partials/alert_log.html")
    history = read_template("history.html")
    fleet = read_template("fleet.html")

    assert "mobile-card-table" in history
    assert "data-label=" in dashboard_alerts
    assert "data-label=" in history

    for label in ["#", "Biển số", "Tên xe", "Device ID", "SĐT Quản lý", "Trạng thái"]:
        assert f'data-label="{label}"' in fleet

    for label in [
        "#",
        "Ảnh mặt",
        "Tên",
        "Tuổi",
        "Giới tính",
        "SĐT",
        "RFID",
        "Điểm an toàn",
        "Mức đánh giá",
        "Trạng thái",
        "Hành động",
    ]:
        assert f'data-label="{label}"' in fleet


def test_css_defines_mobile_dashboard_layout_contract():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "WEBQUANLI MOBILE RESPONSIVE V2" in css
    assert "@media (max-width: 768px)" in css
    assert "@media (max-width: 560px)" in css
    assert ".data-table.mobile-card-table" in css
    assert "content: attr(data-label)" in css
    assert "padding-bottom: calc(92px + env(safe-area-inset-bottom))" in css
    assert "bottom: 0" in css
    assert "#map-container" in css
    assert ".chart-container" in css


def test_professional_ui_assets_use_consistent_tokens():
    base = read_template("base.html")
    fleet = read_template("fleet.html")
    penalties = read_template("penalties.html")
    statistics = read_template("statistics.html")
    css = STYLE_CSS.read_text(encoding="utf-8")
    charts = CHARTS_JS.read_text(encoding="utf-8")

    assert MOBILE_TOKEN in base
    assert f"/static/js/toast.js?v={MOBILE_TOKEN}" in base
    assert "toast-container" in css
    assert "showToast(" in fleet
    assert "alert(" not in fleet
    assert "penalty-summary-grid" in penalties
    assert "penalty-summary-grid" in css
    assert "chartColors" in charts
    assert "#ff2800" not in charts
    assert "Rosso Corsa" not in charts
    assert "statistics-dashboard" in statistics
    assert "stats-hero" in statistics
    assert "stats-overview-strip" in statistics
    assert "stats-kpi-card" in statistics
    assert "kpi-icon-bubble" in statistics
    assert ".statistics-dashboard" in css


def test_base_shell_exposes_mobile_webview_mode_contract():
    base = read_template("base.html")
    css = STYLE_CSS.read_text(encoding="utf-8")
    mobile_js = MOBILE_WEBVIEW_JS.read_text(encoding="utf-8")

    assert 'class="webquanli-shell"' in base
    assert 'data-mobile-title="{% block mobile_title %}' in base
    assert 'id="mobile-app-bar"' in base
    assert 'id="mobile-page-title"' in base
    assert 'id="mobile-connection-pill"' in base
    assert f"/static/js/mobile_webview.js?v={MOBILE_TOKEN}" in base
    assert "WEBQUANLI MOBILE WEBVIEW MODE" in css
    assert "env(safe-area-inset-bottom)" in css
    assert "min-height: 44px" in css
    assert "--webview-vh" in css
    assert "mobile-webview-mode" in mobile_js
    assert "setProperty('--webview-vh'" in mobile_js


def test_core_pages_expose_mobile_page_markers_and_filter_drawers():
    pages = {
        "dashboard.html": "mobile-page-dashboard",
        "history.html": "mobile-page-history",
        "fleet.html": "mobile-page-fleet",
        "penalties.html": "mobile-page-penalties",
        "statistics.html": "mobile-page-statistics",
    }
    for template_name, marker in pages.items():
        assert marker in read_template(template_name)

    history = read_template("history.html")
    penalties = read_template("penalties.html")
    fleet = read_template("fleet.html")
    login = read_template("login.html")

    assert "mobile-filter-drawer" in history
    assert "mobile-filter-summary" in history
    assert "mobile-filter-drawer" in penalties
    assert "mobile-filter-summary" in penalties
    assert "mobile-sheet-panel" in fleet
    assert "mobile-login-shell" in login
    css = STYLE_CSS.read_text(encoding="utf-8")
    assert ".mobile-login-shell .login-container" in css
    assert "max-width: 100vw;" in css
    assert "box-sizing: border-box;" in css


def test_statistics_page_uses_compact_premium_layout_contract():
    statistics = read_template("statistics.html")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "stats-compact-dashboard" in statistics
    assert "stats-compact-strip" in statistics
    assert "chart-compact" in statistics
    assert ".stats-compact-dashboard .stats-hero" in css
    assert "min-height: 92px;" in css
    assert "min-height: 82px;" in css
    assert "min-height: 248px;" in css
    assert "min-height: 292px;" in css


def test_monitoring_dashboard_uses_state_safe_compact_layout_contract():
    dashboard = read_template("dashboard.html")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "monitoring-compact-dashboard" in dashboard
    assert "monitoring-state-strip" in dashboard
    assert "monitoring-hardware-panel" in dashboard
    assert "map-compact-shell" in dashboard
    assert "monitoring-alert-panel" in dashboard
    assert "monitoring-alert-scroll" in dashboard

    for state_marker in [
        "monitoring-session-state",
        "connection-status",
        "verify_snapshot",
        "verify_error",
        "face_mismatch",
        "session_start",
        "session_end",
        "hardware",
        "alert",
    ]:
        assert state_marker in dashboard

    assert ".monitoring-compact-dashboard .trust-hero" in css
    assert ".monitoring-compact-dashboard .overview-chip" in css
    assert ".monitoring-compact-dashboard .hw-badge" in css
    assert ".map-compact-shell" in css
    assert ".monitoring-alert-scroll" in css
    assert "max-height: 280px;" in css


def test_penalties_page_uses_state_safe_compact_layout_contract():
    penalties = read_template("penalties.html")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "penalty-compact-dashboard" in penalties
    assert "penalty-compact-summary" in penalties
    assert "penalty-compact-filter" in penalties
    assert "penalty-table-panel" in penalties
    assert "penalty-scroll-frame" in penalties

    for state_marker in [
        "badge-review-{{ penalty.review_status }}",
        "badge-recommendation-{{ penalty.recommended_action }}",
        "driver_telegram_status",
        "assistant_telegram_status",
        "admin_telegram_status",
        "penalty-note-form",
        'review_status" value="confirmed"',
        'review_status" value="cancelled"',
    ]:
        assert state_marker in penalties

    assert ".penalty-compact-dashboard .summary-card" in css
    assert ".penalty-compact-filter .filter-grid" in css
    assert ".penalty-scroll-frame" in css
    assert ".penalty-compact-dashboard .penalty-note-form textarea" in css
    assert "max-height: 430px;" in css
