# Tailscale WebSocket Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Jetson Nano (`DrowsiGuard-Full.desktop`) connect reliably to WebQuanLi over Tailscale instead of drifting LAN IPs.

**Architecture:** Keep WebQuanLi bound to `0.0.0.0:8000` on Windows and make Jetson use the Windows Tailscale IP as its WebSocket target. Avoid changing application logic; only adjust runtime configuration/launcher values after explicit approval. Verify each network layer before and after changing runtime config.

**Tech Stack:** Windows batch, FastAPI/Uvicorn WebQuanLi, Jetson Nano Linux shell, Tailscale, Version3 `DROWSIGUARD_WS_URL`, WebSocket path `/ws/jetson/JETSON-001`.

---

## Current Evidence

- Windows Tailscale IP observed: `100.91.225.22`
- Jetson Tailscale IP observed: `100.68.19.10`
- Windows LAN IP observed: `192.168.2.11`
- Jetson runtime currently targets old LAN IP:

```text
WSClient initialized target=ws://192.168.2.24:8000/ws/jetson/JETSON-001
WSClient error: [Errno 113] No route to host
```

- Local source fallback in `D:\DATN-testing1\Version3\config.py`:

```python
WS_SERVER_URL = os.environ.get(
    "DROWSIGUARD_WS_URL",
    f"ws://192.168.2.24:8000/ws/jetson/{DEVICE_ID}"
).format(device_id=DEVICE_ID)
```

- WebQuanLi launcher already intends to expose the server outside localhost:

```bat
set "HOST=0.0.0.0"
set "PORT=8000"
```

## Proposed Runtime Target

Use this WebSocket URL on Jetson:

```text
ws://100.91.225.22:8000/ws/jetson/JETSON-001
```

Windows can still open the dashboard locally with:

```text
http://127.0.0.1:8000
```

Jetson should connect to Windows via:

```text
http://100.91.225.22:8000
ws://100.91.225.22:8000/ws/jetson/JETSON-001
```

## Files And Surfaces

### Local Windows Files

- Read/verify only: `D:\DATN-testing1\start_webquanli.bat`
  - It already uses `--host 0.0.0.0 --port 8000`.
- No planned local WebQuanLi code change.
- No planned database migration.
- No planned dashboard UI change.

### Jetson Files, Only After Approval

- Modify: `/home/nano/start_drowsiguard_full.sh`
  - Add an explicit default for `DROWSIGUARD_WS_URL` so desktop launches use Tailscale.
- Modify or create: `/home/nano/Version3/drowsiguard.env`
  - Set the same `DROWSIGUARD_WS_URL` for systemd/service-based starts.
- Do not modify: `/home/nano/Version3/main.py`
- Do not modify: `/home/nano/Version3/network/ws_client.py`
- Do not modify: `/home/nano/Version3/config.py` unless a later approved cleanup wants the default changed in source.

## Rollback

Before editing Jetson files, create backups:

```bash
mkdir -p /home/nano/backup_2026_05_11_tailscale_ws
cp /home/nano/start_drowsiguard_full.sh /home/nano/backup_2026_05_11_tailscale_ws/start_drowsiguard_full.sh
cp /home/nano/Version3/drowsiguard.env /home/nano/backup_2026_05_11_tailscale_ws/drowsiguard.env 2>/dev/null || true
```

Rollback commands:

```bash
cp /home/nano/backup_2026_05_11_tailscale_ws/start_drowsiguard_full.sh /home/nano/start_drowsiguard_full.sh
if [ -f /home/nano/backup_2026_05_11_tailscale_ws/drowsiguard.env ]; then
  cp /home/nano/backup_2026_05_11_tailscale_ws/drowsiguard.env /home/nano/Version3/drowsiguard.env
fi
```

---

### Task 1: Verify WebQuanLi Is Actually Listening On Windows

**Files:**
- Read: `D:\DATN-testing1\start_webquanli.bat`
- No file edits.

- [ ] **Step 1: Run import preflight**

Run on Windows:

```powershell
cmd /c "D:\DATN-testing1\start_webquanli.bat --check"
```

Expected:

```text
Check OK: WebQuanLi imports successfully.
```

- [ ] **Step 2: Start WebQuanLi**

Run by shortcut or command:

```powershell
cmd /c "D:\DATN-testing1\start_webquanli.bat"
```

Expected:

```text
Starting WebQuanLi...
Uvicorn running on http://0.0.0.0:8000
```

Keep this terminal window open.

- [ ] **Step 3: Verify Windows is listening on port 8000**

Run on Windows:

```powershell
cmd /c "netstat -ano | findstr :8000"
```

Expected to include a listener like:

```text
TCP    0.0.0.0:8000    0.0.0.0:0    LISTENING    <pid>
```

If there is no `LISTENING` row, do not continue to Jetson config. WebQuanLi is not running or crashed during startup.

- [ ] **Step 4: Verify local browser path**

Run on Windows:

```powershell
powershell -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 5).StatusCode } catch { $_.Exception.Message }"
```

Expected: HTTP response status or a login redirect response. Not expected: connection refused or timeout.

---

### Task 2: Verify Tailscale Path From Jetson To Windows

**Files:**
- No file edits.

- [ ] **Step 1: Confirm both Tailscale IPs**

Run on Windows:

```powershell
ipconfig
```

Expected Windows Tailscale IP:

```text
100.91.225.22
```

Run on Jetson:

```bash
hostname -I
```

Expected Jetson Tailscale IP:

```text
100.68.19.10
```

- [ ] **Step 2: Test TCP reachability from Jetson**

Run on Jetson:

```bash
python3 - <<'PY'
import socket
target = ("100.91.225.22", 8000)
sock = socket.create_connection(target, timeout=5)
sock.close()
print("TCP_OK", target[0], target[1])
PY
```

Expected:

```text
TCP_OK 100.91.225.22 8000
```

If this times out, check Windows firewall before changing Jetson runtime config.

- [ ] **Step 3: Test HTTP reachability from Jetson**

Run on Jetson:

```bash
curl -sS -m 5 -i http://100.91.225.22:8000/ | head -20
```

Expected: HTTP headers from WebQuanLi, such as `HTTP/1.1 200`, `HTTP/1.1 302`, or `HTTP/1.1 307`.

Not expected:

```text
Connection timed out
No route to host
Connection refused
```

- [ ] **Step 4: If Windows firewall blocks port 8000, add a scoped rule**

Only run if Step 2 or Step 3 fails while WebQuanLi is listening locally.

Run in an elevated Windows PowerShell:

```powershell
New-NetFirewallRule `
  -DisplayName "DrowsiGuard WebQuanLi 8000 from Tailscale" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 8000 `
  -RemoteAddress 100.64.0.0/10
```

Expected: rule creation succeeds. Then rerun Step 2 and Step 3.

---

### Task 3: Configure Jetson Desktop Launcher To Use Tailscale WebSocket

**Files:**
- Modify after approval: `/home/nano/start_drowsiguard_full.sh`

- [ ] **Step 1: Back up the launcher**

Run on Jetson:

```bash
mkdir -p /home/nano/backup_2026_05_11_tailscale_ws
cp /home/nano/start_drowsiguard_full.sh /home/nano/backup_2026_05_11_tailscale_ws/start_drowsiguard_full.sh
```

Expected: backup file exists:

```bash
ls -l /home/nano/backup_2026_05_11_tailscale_ws/start_drowsiguard_full.sh
```

- [ ] **Step 2: Add the WebSocket URL export**

Edit `/home/nano/start_drowsiguard_full.sh`.

Add this line after the existing feature exports and before `python3 main.py`:

```bash
export DROWSIGUARD_WS_URL=${DROWSIGUARD_WS_URL:-ws://100.91.225.22:8000/ws/jetson/JETSON-001}
```

Recommended nearby block:

```bash
export DROWSIGUARD_FEATURE_RFID=true
export DROWSIGUARD_FEATURE_GPS=true
export DROWSIGUARD_FEATURE_SPEAKER=true
export DROWSIGUARD_FEATURE_WEBSOCKET=true
export DROWSIGUARD_WS_URL=${DROWSIGUARD_WS_URL:-ws://100.91.225.22:8000/ws/jetson/JETSON-001}
```

- [ ] **Step 3: Verify shell syntax**

Run on Jetson:

```bash
bash -n /home/nano/start_drowsiguard_full.sh
```

Expected: no output and exit code `0`.

- [ ] **Step 4: Verify the launcher resolves the new URL**

Run on Jetson:

```bash
grep -n 'DROWSIGUARD_WS_URL' /home/nano/start_drowsiguard_full.sh
```

Expected:

```text
export DROWSIGUARD_WS_URL=${DROWSIGUARD_WS_URL:-ws://100.91.225.22:8000/ws/jetson/JETSON-001}
```

---

### Task 4: Configure Jetson Service Env To Use Tailscale WebSocket

**Files:**
- Modify or create after approval: `/home/nano/Version3/drowsiguard.env`

- [ ] **Step 1: Back up env file if it exists**

Run on Jetson:

```bash
mkdir -p /home/nano/backup_2026_05_11_tailscale_ws
cp /home/nano/Version3/drowsiguard.env /home/nano/backup_2026_05_11_tailscale_ws/drowsiguard.env 2>/dev/null || true
```

- [ ] **Step 2: Ensure env file exists**

Run on Jetson:

```bash
cd /home/nano/Version3
if [ ! -f drowsiguard.env ]; then
  cp drowsiguard.env.example drowsiguard.env
fi
```

Expected:

```bash
ls -l /home/nano/Version3/drowsiguard.env
```

- [ ] **Step 3: Set the WebSocket URL in env**

Run on Jetson:

```bash
cd /home/nano/Version3
if grep -q '^DROWSIGUARD_WS_URL=' drowsiguard.env; then
  sed -i 's|^DROWSIGUARD_WS_URL=.*|DROWSIGUARD_WS_URL=ws://100.91.225.22:8000/ws/jetson/JETSON-001|' drowsiguard.env
else
  printf '\nDROWSIGUARD_WS_URL=ws://100.91.225.22:8000/ws/jetson/JETSON-001\n' >> drowsiguard.env
fi
```

- [ ] **Step 4: Verify env value**

Run on Jetson:

```bash
grep -n '^DROWSIGUARD_WS_URL=' /home/nano/Version3/drowsiguard.env
```

Expected:

```text
DROWSIGUARD_WS_URL=ws://100.91.225.22:8000/ws/jetson/JETSON-001
```

---

### Task 5: Restart Runtime In A Controlled Order

**Files:**
- No file edits.

- [ ] **Step 1: Stop old DrowsiGuard runtime if still running**

Run on Jetson:

```bash
pgrep -af 'python3 .*main.py' || true
```

If a process is running, stop it from the launcher terminal with `Ctrl+C`. If the terminal is not available, run:

```bash
pkill -TERM -f 'python3 .*main.py'
sleep 2
pgrep -af 'python3 .*main.py' || true
```

Expected: no `python3 main.py` process remains before relaunch.

- [ ] **Step 2: Start WebQuanLi first**

Run on Windows:

```powershell
cmd /c "D:\DATN-testing1\start_webquanli.bat"
```

Expected:

```text
Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 3: Verify Jetson can reach WebQuanLi before launching DrowsiGuard**

Run on Jetson:

```bash
python3 - <<'PY'
import socket
sock = socket.create_connection(("100.91.225.22", 8000), timeout=5)
sock.close()
print("TCP_OK")
PY
```

Expected:

```text
TCP_OK
```

- [ ] **Step 4: Start DrowsiGuard desktop launcher**

On Jetson desktop, open:

```text
/home/nano/Desktop/DrowsiGuard-Full.desktop
```

Do not run `testgps.py` at the same time because it would compete for `/dev/ttyTHS1`.

---

### Task 6: Verify WebSocket Online End-To-End

**Files:**
- No file edits.

- [ ] **Step 1: Verify Jetson log target URL**

Run on Jetson:

```bash
tail -n 80 /home/nano/Version3/logs/drowsiguard.log | grep -E 'WSClient initialized target|WSClient connected|WSClient error|No route to host'
```

Expected target:

```text
WSClient initialized target=ws://100.91.225.22:8000/ws/jetson/JETSON-001
```

Expected connection:

```text
WSClient connected to backend
```

Not expected:

```text
No route to host
Connection timed out
Connection refused
```

- [ ] **Step 2: Verify dashboard connection badge**

Open on Windows:

```text
http://127.0.0.1:8000
```

Expected dashboard badge:

```text
Kết nối
```

Not expected:

```text
Mất kết nối
```

- [ ] **Step 3: Verify hardware event reaches WebQuanLi**

Run on Jetson:

```bash
tail -n 120 /home/nano/Version3/logs/drowsiguard.log | grep -E 'hardware|Queue=|WSClient connected'
```

Expected: queue stops growing after WebSocket connects. Dashboard hardware badges update from Jetson state.

- [ ] **Step 4: Verify RFID/session event reaches WebQuanLi**

Scan an RFID card once.

Expected on Jetson log:

```text
RFID scanned
SESSION START
```

Expected on WebQuanLi dashboard:

```text
Phiên giám sát: Đang hoạt động
```

If dashboard remains idle while Jetson shows connected, inspect WebQuanLi console for schema/contract errors before changing more code.

---

### Task 7: Final Safety Checks

**Files:**
- No file edits.

- [ ] **Step 1: Confirm GPS still works after launcher starts**

Run on Jetson:

```bash
fuser -v /dev/ttyTHS1 2>&1 || true
```

Expected: `python3 main.py` is the only process holding `/dev/ttyTHS1`.

- [ ] **Step 2: Confirm no WebSocket reconnect loop**

Run on Jetson:

```bash
tail -n 120 /home/nano/Version3/logs/drowsiguard.log | grep -E 'Reconnecting in|No route to host|Connection refused|WSClient connected'
```

Expected: one successful `WSClient connected to backend`, with no continuing reconnect loop after that.

- [ ] **Step 3: Record final evidence**

Collect these outputs for the final report:

```bash
grep -n 'DROWSIGUARD_WS_URL' /home/nano/start_drowsiguard_full.sh /home/nano/Version3/drowsiguard.env
tail -n 60 /home/nano/Version3/logs/drowsiguard.log | grep -E 'WSClient initialized target|WSClient connected|RFID scanned|SESSION START'
```

Expected final report:

```text
WebQuanLi listens on Windows port 8000.
Jetson reaches Windows through Tailscale 100.91.225.22.
Jetson runtime uses ws://100.91.225.22:8000/ws/jetson/JETSON-001.
Dashboard shows connected.
GPS remains available on /dev/ttyTHS1.
```

---

## Stop Conditions

Stop and report before making further changes if any of these occur:

- WebQuanLi cannot listen on `0.0.0.0:8000`.
- Jetson cannot reach `100.91.225.22:8000` even after Windows firewall is checked.
- WebQuanLi accepts TCP but closes WebSocket because `JETSON-001` is not registered in the database.
- DrowsiGuard connects but dashboard remains offline due to browser SSE/session issue.
- GPS stops working after runtime starts.

## Expected Outcome

After the approved fix, `DrowsiGuard-Full.desktop` should connect to WebQuanLi through Tailscale and the dashboard should change from `Mất kết nối` to connected without relying on unstable `192.168.2.x` addresses.
