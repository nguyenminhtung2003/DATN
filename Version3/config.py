"""
DrowsiGuard Version3 — Configuration
All tunable parameters in one place.
GPIO pins are PLACEHOLDERS until real wiring is confirmed.
"""
import os


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default

# ─── Device Identity ───────────────────────────────────────
DEVICE_ID = os.getenv("DROWSIGUARD_DEVICE_ID", "JETSON-001")
APP_VERSION = os.getenv("DROWSIGUARD_APP_VERSION", "Version3")

# ─── Camera ────────────────────────────────────────────────
CAMERA_WIDTH = env_int("DROWSIGUARD_CAMERA_WIDTH", 640)
CAMERA_HEIGHT = env_int("DROWSIGUARD_CAMERA_HEIGHT", 360)
CAMERA_FPS = env_int("DROWSIGUARD_CAMERA_FPS", 30)
AI_TARGET_FPS = 12
MAX_NUM_FACES = 1
FACE_MESH_MIN_DETECTION_CONFIDENCE = float(os.getenv("DROWSIGUARD_FACE_MESH_MIN_DETECTION_CONFIDENCE", "0.2"))
FACE_MESH_MIN_TRACKING_CONFIDENCE = float(os.getenv("DROWSIGUARD_FACE_MESH_MIN_TRACKING_CONFIDENCE", "0.2"))

GSTREAMER_PIPELINE = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM), width=1280, height=720, framerate={fps}/1 ! "
    "nvvidconv flip-method=0 ! "
    "video/x-raw, width={w}, height={h}, format=BGRx ! "
    "videoconvert ! video/x-raw, format=BGR ! "
    "appsink drop=true sync=false"
).format(w=CAMERA_WIDTH, h=CAMERA_HEIGHT, fps=CAMERA_FPS)

CAMERA_RECONNECT_DELAY = 3.0
CAMERA_WATCHDOG_TIMEOUT = 5.0

# ─── Drowsiness Thresholds (default fallback) ─────────────
EAR_THRESHOLD = env_float("DROWSIGUARD_EAR_THRESHOLD", 0.24)
MAR_THRESHOLD = env_float("DROWSIGUARD_MAR_THRESHOLD", 0.45)
PITCH_DELTA_THRESHOLD = env_float("DROWSIGUARD_PITCH_DELTA_THRESHOLD", -15.0)
PERCLOS_THRESHOLD = env_float("DROWSIGUARD_PERCLOS_THRESHOLD", 0.55)

# Smoothing
EAR_SMOOTHING_ALPHA = 0.3
MAR_SMOOTHING_ALPHA = 0.3
PITCH_SMOOTHING_ALPHA = 0.3

# Eye quality checks for drivers wearing prescription glasses.
EYE_EAR_MIN = env_float("DROWSIGUARD_EYE_EAR_MIN", 0.05)
EYE_EAR_MAX = env_float("DROWSIGUARD_EYE_EAR_MAX", 0.45)
EYE_MIN_WIDTH_PX = env_int("DROWSIGUARD_EYE_MIN_WIDTH_PX", 8)
EYE_GLARE_PIXEL_THRESHOLD = env_int("DROWSIGUARD_EYE_GLARE_PIXEL_THRESHOLD", 245)
EYE_GLARE_RATIO_THRESHOLD = env_float("DROWSIGUARD_EYE_GLARE_RATIO_THRESHOLD", 0.55)
EYE_ASYMMETRY_THRESHOLD = env_float("DROWSIGUARD_EYE_ASYMMETRY_THRESHOLD", 0.12)

# ─── Alert Timing ──────────────────────────────────────────
LEVEL1_DURATION = 2.0
LEVEL2_DURATION = 4.0
LEVEL3_DURATION = 6.0
ALERT_COOLDOWN = 3.0

YAWN_COUNT_WINDOW = 60.0
YAWN_COUNT_THRESHOLD = 2

PERCLOS_WINDOW = env_float("DROWSIGUARD_PERCLOS_WINDOW", 8.0)

# AI classifier (lightweight feature classifier, not a heavy CNN)
AI_CLASSIFIER_ENABLED = env_bool("DROWSIGUARD_AI_CLASSIFIER_ENABLED", True)
AI_CLASSIFIER_WINDOW_SECONDS = env_float("DROWSIGUARD_AI_WINDOW_SECONDS", 2.0)
AI_THERMAL_WARN_C = float(os.getenv("DROWSIGUARD_AI_THERMAL_WARN_C", "75"))
AI_THERMAL_CRITICAL_C = float(os.getenv("DROWSIGUARD_AI_THERMAL_CRITICAL_C", "80"))
AI_THROTTLED_TARGET_FPS = float(os.getenv("DROWSIGUARD_AI_THROTTLED_TARGET_FPS", "8"))
AI_MIN_STABLE_FPS = float(os.getenv("DROWSIGUARD_AI_MIN_STABLE_FPS", "7"))

# ─── Calibration ──────────────────────────────────────────
CALIBRATION_DURATION = 7.0
CALIBRATION_MIN_SAMPLES = 30

# ─── Reverification ───────────────────────────────────────
REVERIFY_INTERVAL = 300
REVERIFY_FAST_INTERVAL = 180
REVERIFY_MAX_CONSECUTIVE_FAILS = 2

# ─── Hardware Pins (PLACEHOLDER — not confirmed) ──────────
# These MUST be updated once real wiring is done.
HAS_BUZZER = env_bool("DROWSIGUARD_FEATURE_BUZZER", False)
HAS_LED = env_bool("DROWSIGUARD_FEATURE_LED", False)
HAS_SPEAKER = env_bool("DROWSIGUARD_FEATURE_SPEAKER", False)
HAS_GPS = env_bool("DROWSIGUARD_FEATURE_GPS", False)

BUZZER_RELAY_PIN = 18      # placeholder
LED_WARNING_PIN = 16       # placeholder
LED_CRITICAL_PIN = 22      # placeholder

# ─── GPS ───────────────────────────────────────────────────
GPS_PORT = "/dev/ttyTHS1"
GPS_BAUDRATE = 9600
GPS_SEND_INTERVAL = 3.0

# Local runtime/dashboard
RUNTIME_DIR = os.getenv("DROWSIGUARD_RUNTIME_DIR", os.path.join(os.path.dirname(__file__), "storage", "runtime"))
DASHBOARD_PORT = int(os.getenv("DROWSIGUARD_DASHBOARD_PORT", "8080"))
DASHBOARD_TOKEN = os.getenv("DROWSIGUARD_DASHBOARD_TOKEN", "")
DASHBOARD_SNAPSHOT_INTERVAL = float(os.getenv("DROWSIGUARD_DASHBOARD_SNAPSHOT_INTERVAL", "0.75"))
DASHBOARD_SNAPSHOT_SLOW_INTERVAL = float(os.getenv("DROWSIGUARD_DASHBOARD_SNAPSHOT_SLOW_INTERVAL", "1.5"))
DASHBOARD_SNAPSHOT_QUALITY = int(os.getenv("DROWSIGUARD_DASHBOARD_SNAPSHOT_QUALITY", "65"))
DASHBOARD_SERVICE_CONTROL = env_bool("DROWSIGUARD_DASHBOARD_SERVICE_CONTROL", False)

# Local OpenCV monitor for manual testing on the Jetson display/NoMachine.
# This is disabled for systemd/service mode to keep the production runtime lean.
LOCAL_GUI_ENABLED = env_bool("DROWSIGUARD_LOCAL_GUI", env_bool("DROWSIGUARD_LOCAL_GUI_ENABLED", False))
LOCAL_GUI_FPS = int(os.getenv("DROWSIGUARD_LOCAL_GUI_FPS", "10"))
LOCAL_GUI_WIDTH = int(os.getenv("DROWSIGUARD_LOCAL_GUI_WIDTH", "960"))
LOCAL_GUI_TEST_KEYS = env_bool("DROWSIGUARD_LOCAL_GUI_TEST_KEYS", True)

# Bluetooth speaker/audio
BLUETOOTH_SPEAKER_MAC = os.getenv("DROWSIGUARD_BLUETOOTH_SPEAKER_MAC", "")
AUDIO_BACKEND = os.getenv("DROWSIGUARD_AUDIO_BACKEND", "auto")
AUDIO_ALERT_LEVEL1 = os.getenv("DROWSIGUARD_AUDIO_ALERT_LEVEL1", os.path.join(os.path.dirname(__file__), "sounds", "alert_level1.wav"))
AUDIO_ALERT_LEVEL2 = os.getenv("DROWSIGUARD_AUDIO_ALERT_LEVEL2", os.path.join(os.path.dirname(__file__), "sounds", "alert_level2.wav"))
AUDIO_ALERT_LEVEL3 = os.getenv("DROWSIGUARD_AUDIO_ALERT_LEVEL3", os.path.join(os.path.dirname(__file__), "sounds", "alert_level3.wav"))

# ─── RFID (USB HID) ───────────────────────────────────────
RFID_DEVICE_PATH = os.getenv("DROWSIGUARD_RFID_DEVICE_PATH") or None  # e.g. "/dev/input/event3"
RFID_DEBOUNCE_SEC = 2.0
RFID_GRAB_EXCLUSIVE = True

# ─── WebSocket ─────────────────────────────────────────────
WS_SERVER_URL = os.environ.get(
    "DROWSIGUARD_WS_URL",
    f"ws://192.168.2.24:8000/ws/jetson/{DEVICE_ID}"
).format(device_id=DEVICE_ID)
WS_RECONNECT_BASE = 1.0
WS_RECONNECT_MAX = 60.0

# ─── Local Store ───────────────────────────────────────────
QUEUE_DB_PATH = os.path.join(os.path.dirname(__file__), "storage", "local_events.db")
QUEUE_MAX_RECORDS = 1000

# ─── Hardware Monitor ─────────────────────────────────────
HW_REPORT_INTERVAL = 5.0
MONITORING_AUTOSTART = env_bool("DROWSIGUARD_MONITORING_AUTOSTART", False)

# ─── OTA ───────────────────────────────────────────────────
OTA_DOWNLOAD_DIR = "/tmp/drowsiguard_ota"
OTA_PROJECT_DIR = os.path.dirname(__file__)
OTA_BACKUP_DIR = os.path.join(os.path.dirname(__file__), "_backup")

# ─── Logging ───────────────────────────────────────────────
LOG_LEVEL = os.getenv("DROWSIGUARD_LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(os.path.dirname(__file__), "logs", "drowsiguard.log")
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3

# ─── Verification Flow Config ──────────────────────────────
# Directory to store local reference images and registry manifest
FACE_DATA_DIR = os.path.join(os.path.dirname(__file__), "storage", "driver_faces")
FACE_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "storage", "driver_registry.json")
FACE_VERIFY_THRESHOLD = float(os.getenv("DROWSIGUARD_FACE_VERIFY_THRESHOLD", "0.82"))
FACE_VERIFY_METHOD = os.getenv("DROWSIGUARD_FACE_VERIFY_METHOD", "auto")
FACE_LBPH_THRESHOLD = float(os.getenv("DROWSIGUARD_FACE_LBPH_THRESHOLD", "60.0"))
FACE_CROP_PADDING_RATIO = float(os.getenv("DROWSIGUARD_FACE_CROP_PADDING", "0.18"))
FACE_VERIFY_ACQUIRE_TIMEOUT_SEC = float(os.getenv("DROWSIGUARD_FACE_VERIFY_ACQUIRE_TIMEOUT", "1.5"))
FACE_VERIFY_ACQUIRE_POLL_SEC = float(os.getenv("DROWSIGUARD_FACE_VERIFY_ACQUIRE_POLL", "0.15"))
FACE_SYNC_TIMEOUT_SEC = float(os.getenv("DROWSIGUARD_FACE_SYNC_TIMEOUT", "10.0"))

# Prevent auto-allow logic in production. Set to True ONLY for testing without face db.
DEMO_MODE_ALLOW_UNVERIFIED = env_bool("DROWSIGUARD_DEMO_MODE", False)
LOCAL_GUI_AUTOSTART_SESSION = env_bool(
    "DROWSIGUARD_LOCAL_GUI_AUTOSTART_SESSION",
    LOCAL_GUI_ENABLED and DEMO_MODE_ALLOW_UNVERIFIED,
)

# ─── Feature Flags for deferred hardware ──────────────────
FEATURES = {
    "camera": env_bool("DROWSIGUARD_FEATURE_CAMERA", True),
    "drowsiness": env_bool("DROWSIGUARD_FEATURE_DROWSINESS", True),
    "rfid": env_bool("DROWSIGUARD_FEATURE_RFID", True),
    "gps": HAS_GPS,
    "buzzer": HAS_BUZZER,
    "led": HAS_LED,
    "speaker": HAS_SPEAKER,
    "websocket": env_bool("DROWSIGUARD_FEATURE_WEBSOCKET", True),
    "ota": env_bool("DROWSIGUARD_FEATURE_OTA", True),
    "face_verify": env_bool("DROWSIGUARD_FEATURE_FACE_VERIFY", True),
}
