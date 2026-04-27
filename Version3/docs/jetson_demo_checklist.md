# DrowsiGuard Version3 Jetson Demo Checklist

Use this checklist on the Jetson Nano A02 before a real demo.

## 1. Network and Time

Check the current IP addresses:

```bash
ip -4 addr show eth0
ip -4 addr show wlan0
hostname -I
```

When using phone hotspot Wi-Fi, edit WebQuanLi and Jetson to use the hotspot LAN IPs instead of the fixed Ethernet IP.

The Jetson clock must be correct before demo logs:

```bash
date
timedatectl status
```

If the clock is wrong and the Jetson has internet:

```bash
sudo timedatectl set-ntp true
```

## 2. Runtime Config

Edit:

```bash
nano /home/nano/Version3/drowsiguard.env
```

Minimum demo values:

```bash
DROWSIGUARD_DEVICE_ID=JETSON-001
DROWSIGUARD_DEMO_MODE=false
DROWSIGUARD_WS_URL=ws://WEBQUANLI_IP:8000/ws/jetson/JETSON-001
DROWSIGUARD_FEATURE_SPEAKER=true
DROWSIGUARD_BLUETOOTH_SPEAKER_MAC=AA:BB:CC:DD:EE:FF
DROWSIGUARD_DASHBOARD_SERVICE_CONTROL=false
```

Restart after changes:

```bash
sudo systemctl restart drowsiguard drowsiguard-dashboard
```

## 3. Required Python/System Packages

When the Jetson has internet, install the missing runtime packages:

```bash
sudo apt-get update
sudo apt-get install -y python3-websocket python3-evdev
```

`python3-websocket` is required for WebQuanLi realtime connection.
`python3-evdev` is required for the USB RFID reader.

## 4. Bluetooth Speaker

Plug the USB Bluetooth dongle first, then check:

```bash
bluetoothctl list
bluetoothctl show
```

Pair and trust the car speaker:

```bash
bluetoothctl
power on
agent on
default-agent
scan on
pair AA:BB:CC:DD:EE:FF
trust AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
quit
```

Then set `DROWSIGUARD_FEATURE_SPEAKER=true` and `DROWSIGUARD_BLUETOOTH_SPEAKER_MAC` in `drowsiguard.env`.

Test audio:

```bash
curl -X POST http://127.0.0.1:8080/api/alerts/test/1
curl -X POST http://127.0.0.1:8080/api/alerts/test/2
curl -X POST http://127.0.0.1:8080/api/alerts/test/3
```

## 5. Dashboard

Open from a laptop/phone on the same network:

```text
http://JETSON_IP:8080
```

Expected dashboard status:

- camera online with live snapshot
- strict mode enabled
- WebSocket connected after WebQuanLi IP is configured
- Bluetooth speaker connected after dongle/speaker pairing
- RFID dependency passing after `python3-evdev` install
- no restart-service button unless you explicitly enable `DROWSIGUARD_DASHBOARD_SERVICE_CONTROL=true`

## 6. Healthcheck

Run:

```bash
cd /home/nano/Version3
python3 healthcheck.py --quick
```

Acceptable warnings before final hardware is connected:

- `bluetooth_adapter` if the USB Bluetooth dongle is not plugged in
- `rfid_dependency` before `python3-evdev` is installed
- `websocket_url` while `SERVER_IP` is still a placeholder

For demo day, those three should be resolved.
