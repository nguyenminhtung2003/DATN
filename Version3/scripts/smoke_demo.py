import sys
import os
import time
import threading
from unittest.mock import MagicMock

# Mock hardware dependencies so smoke demo can run on host PC
sys.modules['cv2'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['evdev'] = MagicMock()
sys.modules['smbus2'] = MagicMock()
sys.modules['mediapipe'] = MagicMock()

# Add parent path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import DrowsiGuard
import config

# Override config for smoke test
config.FEATURES = {
    "camera": False,
    "drowsiness": False,
    "rfid": False,
    "gps": False,
    "buzzer": False,
    "led": False,
    "speaker": False,
    "websocket": False,  # Turn off actual WS out to avoid connecting randomly
    "ota": False,
    "face_verify": False,
}
# Enable demo mode explicitly
config.DEMO_MODE_ALLOW_UNVERIFIED = True

print("==================================================")
print("🚀 STARTING SMOKE DEMO (Helper Script) ")
print("==================================================")

app = DrowsiGuard()

# 1. Start Session
print("\n>>> [STEP 1] SIMULATING RFID SCAN (UID-SMOKE)")
app._on_rfid_scan("UID-SMOKE")
time.sleep(1)

# 2. Simulate Backend Command: Test Alert
print("\n>>> [STEP 2] SIMULATING BACKEND COMMAND: test_alert")
app._on_backend_command({"action": "test_alert", "level": 2, "state": "on"})
time.sleep(1.5)
app._on_backend_command({"action": "test_alert", "level": 2, "state": "off"})

# 3. Simulate Backend Command: OTA Update
print("\n>>> [STEP 3] SIMULATING BACKEND COMMAND: update_software")
app._on_backend_command({"action": "update_software", "filename": "v2.0.FINAL.zip", "download_url": "http://example.com/ota"})
time.sleep(5)  # give OTA simulation thread time to finish

# 4. End Session
print("\n>>> [STEP 4] SIMULATING RFID SCAN TO END SESSION")
app._on_rfid_scan("UID-SMOKE")
time.sleep(1)

print("\n==================================================")
print("✅ SMOKE DEMO COMPLETED SUCCESSFULLY!")
print("==================================================")

app._shutdown()
