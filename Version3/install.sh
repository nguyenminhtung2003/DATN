#!/bin/bash
# DrowsiGuard Version3 - Installation Script for Jetson Nano A02
# Run: sudo bash install.sh

set -e

echo "=================================="
echo "DrowsiGuard Version3 Installer"
echo "=================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER="${DROWSIGUARD_SERVICE_USER:-${SUDO_USER:-nano}}"
DASHBOARD_PORT="${DROWSIGUARD_DASHBOARD_PORT:-8080}"

echo "[1/5] Installing system dependencies..."
if [ "${DROWSIGUARD_SKIP_APT:-0}" = "1" ]; then
  echo "  Skipping apt dependency installation (DROWSIGUARD_SKIP_APT=1)"
else
  apt-get update -qq
  apt-get install -y -qq python3-pip python3-dev python3-websocket python3-evdev v4l-utils bluez pulseaudio-utils
fi

echo "[2/5] Installing Python dependencies..."
if [ "${DROWSIGUARD_SKIP_PIP:-0}" = "1" ]; then
  echo "  Skipping pip dependency installation (DROWSIGUARD_SKIP_PIP=1)"
else
  pip3 install -r "$SCRIPT_DIR/requirements.txt"
fi

echo "[3/5] Creating runtime directories..."
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/storage"
mkdir -p "$SCRIPT_DIR/storage/runtime"
mkdir -p "$SCRIPT_DIR/sounds"
mkdir -p "$SCRIPT_DIR/_backup"
if [ ! -f "$SCRIPT_DIR/drowsiguard.env" ] && [ -f "$SCRIPT_DIR/drowsiguard.env.example" ]; then
  echo "  Creating local environment file: $SCRIPT_DIR/drowsiguard.env"
  cp "$SCRIPT_DIR/drowsiguard.env.example" "$SCRIPT_DIR/drowsiguard.env"
fi
if [ "$SERVICE_USER" != "root" ]; then
  chown -R "$SERVICE_USER:$SERVICE_USER" \
    "$SCRIPT_DIR/logs" \
    "$SCRIPT_DIR/storage" \
    "$SCRIPT_DIR/_backup" \
    "$SCRIPT_DIR/drowsiguard.env" 2>/dev/null || true
fi

echo "  Installing hardware udev rules..."
UDEV_RULES_FILE="/etc/udev/rules.d/99-drowsiguard-hardware.rules"
cat > "$UDEV_RULES_FILE" <<'RULES'
# DrowsiGuard Jetson Nano A02 GPS UART and USB RFID permissions.
SUBSYSTEM=="tty", KERNEL=="ttyTHS1", GROUP="tty", MODE="0660"
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_VENDOR_ID}=="ffff", ENV{ID_MODEL_ID}=="0035", GROUP="plugdev", MODE="0660", SYMLINK+="input/drowsiguard-rfid"
RULES
udevadm control --reload-rules || true
udevadm trigger --subsystem-match=tty || true
udevadm trigger --subsystem-match=input || true
udevadm settle || true

echo "[4/5] Installing systemd services..."
MAIN_SERVICE_FILE="/etc/systemd/system/drowsiguard.service"
DASHBOARD_SERVICE_FILE="/etc/systemd/system/drowsiguard-dashboard.service"

if [ "$SERVICE_USER" = "root" ]; then
  echo "  Service user: root (only use this when RFID/GPIO permissions require it)"
else
  echo "  Service user: $SERVICE_USER"
fi

sed \
  -e "s|@APP_DIR@|$SCRIPT_DIR|g" \
  -e "s|@SERVICE_USER@|$SERVICE_USER|g" \
  "$SCRIPT_DIR/drowsiguard.service.template" > "$MAIN_SERVICE_FILE"

sed \
  -e "s|@APP_DIR@|$SCRIPT_DIR|g" \
  -e "s|@SERVICE_USER@|$SERVICE_USER|g" \
  -e "s|@DASHBOARD_PORT@|$DASHBOARD_PORT|g" \
  "$SCRIPT_DIR/drowsiguard-dashboard.service.template" > "$DASHBOARD_SERVICE_FILE"

systemctl daemon-reload
systemctl enable drowsiguard.service
systemctl enable drowsiguard-dashboard.service
echo "  Services installed and enabled (will start on next boot)"

echo "[5/5] Running environment check..."
python3 "$SCRIPT_DIR/healthcheck.py" --quick

echo ""
echo "=================================="
echo "Installation complete!"
echo "  Start now:   sudo systemctl start drowsiguard"
echo "               sudo systemctl start drowsiguard-dashboard"
echo "  View logs:   journalctl -u drowsiguard -f"
echo "  Dashboard:   http://<JETSON_IP>:$DASHBOARD_PORT"
echo "=================================="
