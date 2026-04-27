"""Lightweight local dashboard for Jetson-side operations."""
import os
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

import config
from alerts.speaker import Speaker
from audio.bluetooth_manager import BluetoothManager
from storage.runtime_status import RuntimeStatusStore


INDEX_HTML = """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DrowsiGuard Version3</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #101418; color: #f3f5f7; }
    header { padding: 16px 20px; background: #1d252d; border-bottom: 1px solid #33414d; }
    main { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); padding: 16px; }
    section { border: 1px solid #33414d; border-radius: 8px; padding: 14px; background: #151b21; }
    h1, h2 { margin: 0 0 10px; }
    dl { display: grid; grid-template-columns: 120px 1fr; gap: 6px; margin: 0; }
    dt { color: #9fb0bf; }
    dd { margin: 0; word-break: break-word; }
    img { width: 100%; border-radius: 8px; background: #0b0f13; }
    button { border: 1px solid #6b7c8f; border-radius: 6px; background: #243240; color: white; padding: 8px 10px; margin: 4px 4px 0 0; }
    .full { grid-column: 1 / -1; }
  </style>
</head>
<body>
  <header><h1>DrowsiGuard Version3 Local Dashboard</h1></header>
  <main>
    <section><h2>Device</h2><dl id="device"></dl></section>
    <section><h2>System</h2><dl id="system"></dl></section>
    <section><h2>Network</h2><dl id="network"></dl></section>
    <section><h2>WebSocket</h2><dl id="websocket"></dl></section>
    <section><h2>Bluetooth</h2><dl id="bluetooth"></dl>
      <button onclick="reconnectBluetooth()">Reconnect Bluetooth</button>
    </section>
    <section><h2>Audio</h2><dl id="audio"></dl>
      <button onclick="testAudio(1)">Test Level 1</button>
      <button onclick="testAudio(2)">Test Level 2</button>
      <button onclick="testAudio(3)">Test Level 3</button>
      <button onclick="stopAudio()">Stop Audio</button>
    </section>
    <section><h2>AI</h2><dl id="ai"></dl></section>
    <section><h2>Driver</h2><dl id="driver"></dl></section>
    <section><h2>Session</h2><dl id="session"></dl></section>
    <section><h2>Alert</h2><dl id="alert"></dl></section>
    <section><h2>Queue</h2><dl id="queue"></dl></section>
    <section><h2>Hardware</h2><dl id="hardware"></dl></section>
    <section><h2>OTA</h2><dl id="ota"></dl>
      __SERVICE_CONTROL_BUTTON__
    </section>
    <section class="full"><h2>Camera</h2><dl id="camera"></dl><img id="snapshot" src="/api/camera/latest.jpg"></section>
  </main>
  <script>
    function formatValue(value) {
      if (value === null || value === undefined || value === '') return '-';
      if (typeof value === 'object') return JSON.stringify(value);
      return String(value);
    }
    function fill(id, obj) {
      const el = document.getElementById(id);
      el.innerHTML = Object.keys(obj || {}).map(k => `<dt>${k}</dt><dd>${formatValue(obj[k])}</dd>`).join('');
    }
    async function refresh() {
      const res = await fetch('/api/status');
      const status = await res.json();
      ['device', 'system', 'network', 'websocket', 'bluetooth', 'audio', 'ai', 'driver', 'session', 'alert', 'queue', 'hardware', 'ota', 'camera']
        .forEach(key => fill(key, status[key]));
      document.getElementById('snapshot').src = '/api/camera/latest.jpg?ts=' + Date.now();
    }
    async function testAudio(level) {
      await fetch('/api/audio/test/' + level, {method: 'POST'});
      refresh();
    }
    async function stopAudio() {
      await fetch('/api/audio/stop', {method: 'POST'});
      refresh();
    }
    async function reconnectBluetooth() {
      await fetch('/api/bluetooth/reconnect', {method: 'POST'});
      refresh();
    }
    async function restartMain() {
      await fetch('/api/service/restart-main', {method: 'POST'});
      refresh();
    }
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


class ServiceController:
    def __init__(self, enabled=None):
        self.enabled = config.DASHBOARD_SERVICE_CONTROL if enabled is None else bool(enabled)

    def restart_main(self):
        if not self.enabled:
            return {
                "ok": False,
                "service": "drowsiguard.service",
                "error": "service control disabled; enable DROWSIGUARD_DASHBOARD_SERVICE_CONTROL=true to use this endpoint",
            }
        try:
            subprocess.check_output(
                ["systemctl", "restart", "drowsiguard.service"],
                stderr=subprocess.STDOUT,
                timeout=15,
            )
            return {"ok": True, "service": "drowsiguard.service"}
        except Exception as exc:
            return {"ok": False, "service": "drowsiguard.service", "error": str(exc)}


def create_app(runtime_dir=None, speaker=None, bluetooth_manager=None, service_controller=None):
    app = FastAPI(title="DrowsiGuard Version3 Dashboard")
    store = RuntimeStatusStore(runtime_dir)
    speaker = speaker or Speaker()
    bluetooth_manager = bluetooth_manager or BluetoothManager()
    service_controller = service_controller or ServiceController()
    service_control_button = ""
    if getattr(service_controller, "enabled", False):
        service_control_button = '<button onclick="restartMain()">Restart Main Service</button>'

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(INDEX_HTML.replace("__SERVICE_CONTROL_BUTTON__", service_control_button))

    @app.get("/api/status")
    def status():
        payload = store.read()
        payload["bluetooth"] = bluetooth_manager.status()
        if hasattr(speaker, "status"):
            payload["audio"] = speaker.status()
        return payload

    @app.get("/api/health")
    def health():
        payload = store.read()
        return {
            "ok": True,
            "service": "drowsiguard-dashboard",
            "device_id": payload.get("device", {}).get("device_id"),
        }

    @app.get("/api/network/status")
    def network_status():
        return status().get("network", {})

    @app.get("/api/camera/latest.jpg")
    def latest_snapshot():
        path = os.path.join(str(store.runtime_dir), "latest.jpg")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="snapshot not available")
        with open(path, "rb") as fh:
            return Response(content=fh.read(), media_type="image/jpeg")

    @app.get("/api/bluetooth/status")
    def bluetooth_status():
        return bluetooth_manager.status()

    @app.post("/api/bluetooth/reconnect")
    def bluetooth_reconnect():
        return bluetooth_manager.reconnect()

    def _play_test_alert(level: int):
        if level not in (1, 2, 3):
            raise HTTPException(status_code=400, detail="level must be 1, 2 or 3")
        return {"ok": bool(speaker.play_alert(level)), "level": level}

    @app.post("/api/audio/test/{level}")
    def audio_test(level: int):
        return _play_test_alert(level)

    @app.post("/api/alerts/test/{level}")
    def alerts_test(level: int):
        return _play_test_alert(level)

    @app.post("/api/audio/stop")
    def audio_stop():
        speaker.stop()
        return {"ok": True}

    @app.post("/api/service/restart-main")
    def restart_main_service():
        return service_controller.restart_main()

    return app


app = create_app()
