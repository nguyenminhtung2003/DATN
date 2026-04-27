// ══════════════════════════════════════════════
// Leaflet Map — GPS Tracking
// ══════════════════════════════════════════════

let map = null;
let marker = null;
let alertMarkers = [];

function initMap() {
    const mapEl = document.getElementById('map');
    if (!mapEl || map) return;

    const initialLat = parseFloat(mapEl.dataset.lat || '10.762622');
    const initialLng = parseFloat(mapEl.dataset.lng || '106.660172');
    const initialSpeed = parseFloat(mapEl.dataset.speed || '0');
    const hasInitialGps = !Number.isNaN(initialLat) && !Number.isNaN(initialLng);
    const initialPosition = hasInitialGps ? [initialLat, initialLng] : [10.762622, 106.660172];

    map = L.map('map', {
        zoomControl: true,
        attributionControl: false,
    }).setView(initialPosition, hasInitialGps ? 15 : 13);

    // Dark tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
    }).addTo(map);

    // Vehicle marker
    const vehicleIcon = L.divIcon({
        className: 'vehicle-marker',
        html: '<div style="font-size:28px;text-shadow:0 0 8px rgba(88,166,255,0.6);">🚗</div>',
        iconSize: [32, 32],
        iconAnchor: [16, 16],
    });

    marker = L.marker(initialPosition, { icon: vehicleIcon }).addTo(map);
    if (hasInitialGps) {
        marker.bindPopup(
            `<b>📍 Vị trí gần nhất</b><br>` +
            `Lat: ${initialLat.toFixed(6)}<br>` +
            `Lng: ${initialLng.toFixed(6)}<br>` +
            `Tốc độ: ${Number.isNaN(initialSpeed) ? 'N/A' : initialSpeed.toFixed(1) + ' km/h'}`
        );
    } else {
        marker.bindPopup('<b>Xe đang chờ GPS...</b>');
    }
}

function updateMap(lat, lng, speed) {
    if (!map) initMap();
    if (!lat || !lng) return;

    const pos = [lat, lng];
    marker.setLatLng(pos);
    map.panTo(pos, { animate: true, duration: 0.5 });

    const speedText = speed ? `${speed.toFixed(1)} km/h` : 'N/A';
    marker.setPopupContent(
        `<b>📍 Vị trí hiện tại</b><br>` +
        `Lat: ${lat.toFixed(6)}<br>` +
        `Lng: ${lng.toFixed(6)}<br>` +
        `Tốc độ: ${speedText}`
    );
}

function addAlertMarker(lat, lng, level) {
    if (!map || !lat || !lng) return;

    const colors = {
        'LEVEL_1': '#388bfd',
        'LEVEL_2': '#d29922',
        'LEVEL_3': '#f85149',
        'CRITICAL': '#ff0000',
    };

    const color = colors[level] || '#f85149';
    const alertIcon = L.divIcon({
        className: 'alert-marker',
        html: `<div style="width:12px;height:12px;border-radius:50%;background:${color};box-shadow:0 0 8px ${color};border:2px solid #fff;"></div>`,
        iconSize: [12, 12],
        iconAnchor: [6, 6],
    });

    const m = L.marker([lat, lng], { icon: alertIcon }).addTo(map);
    m.bindPopup(`<b>⚠️ Cảnh báo ${level}</b><br>Lat: ${lat.toFixed(4)}, Lng: ${lng.toFixed(4)}`);
    alertMarkers.push(m);
}

// Auto-init map when DOM ready
document.addEventListener('DOMContentLoaded', initMap);
