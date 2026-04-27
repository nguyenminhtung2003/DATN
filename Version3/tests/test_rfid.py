#!/usr/bin/env python3
"""
Hardware Test: RFID USB HID Reader
Detects USB RFID device, reads scanned UIDs via evdev.
Run on Jetson: sudo python3 tests/test_rfid.py
(sudo may be needed for input device access)
"""
import sys
import os
import time
import pytest

pytestmark = pytest.mark.hardware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def discover_devices():
    """List all input devices for manual identification."""
    try:
        import evdev
    except ImportError:
        print("FAIL: 'evdev' not installed. Run: pip3 install evdev")
        return False

    print("=" * 50)
    print("USB RFID Reader Test (HID/evdev)")
    print("=" * 50)

    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    if not devices:
        print("FAIL: No input devices found. Are you running as root/sudo?")
        return False

    print(f"\nFound {len(devices)} input device(s):\n")
    for dev in devices:
        caps = dev.capabilities(verbose=True)
        has_keys = any("EV_KEY" in str(c) for c in caps)
        print(f"  Path: {dev.path}")
        print(f"  Name: {dev.name}")
        print(f"  Phys: {dev.phys}")
        print(f"  Has keys: {has_keys}")
        print()

    return True


def test_rfid_read():
    """Attempt to read a card UID from the RFID reader."""
    import evdev
    from evdev import InputDevice, categorize, ecodes

    # Try to find RFID device
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    rfid_dev = None
    for dev in devices:
        name_lower = dev.name.lower()
        if any(kw in name_lower for kw in ["rfid", "hid", "card", "reader", "rf"]):
            rfid_dev = dev
            break

    if not rfid_dev:
        print("\nNo RFID-specific device auto-detected.")
        print("Please identify the device from the list above and set RFID_DEVICE_PATH in config.py")
        # Try first available keyboard-like device as fallback
        for dev in devices:
            caps = dev.capabilities()
            if ecodes.EV_KEY in caps:
                rfid_dev = dev
                print(f"\nFallback: Using {dev.path} ({dev.name})")
                break

    if not rfid_dev:
        print("FAIL: No suitable input device found for RFID test")
        return False

    print(f"\nUsing RFID device: {rfid_dev.path} — {rfid_dev.name}")
    print("Scan a card now... (waiting 30 seconds)\n")

    KEY_MAP = {
        ecodes.KEY_0: "0", ecodes.KEY_1: "1", ecodes.KEY_2: "2",
        ecodes.KEY_3: "3", ecodes.KEY_4: "4", ecodes.KEY_5: "5",
        ecodes.KEY_6: "6", ecodes.KEY_7: "7", ecodes.KEY_8: "8",
        ecodes.KEY_9: "9",
        ecodes.KEY_A: "A", ecodes.KEY_B: "B", ecodes.KEY_C: "C",
        ecodes.KEY_D: "D", ecodes.KEY_E: "E", ecodes.KEY_F: "F",
    }

    uid_buffer = []
    timeout = time.time() + 30

    try:
        rfid_dev.grab()
        print("Exclusive grab acquired")
    except Exception as e:
        print(f"Warning: Could not grab exclusively: {e}")

    try:
        for event in rfid_dev.read_loop():
            if time.time() > timeout:
                print("TIMEOUT: No card scanned in 30 seconds")
                break

            if event.type != ecodes.EV_KEY:
                continue

            key_event = categorize(event)
            if key_event.keystate != 1:
                continue

            keycode = key_event.scancode
            if keycode == ecodes.KEY_ENTER:
                uid = "".join(uid_buffer).strip()
                uid_buffer.clear()
                if uid:
                    print(f"SUCCESS: Card UID = {uid}")
                    print(f"  Raw length: {len(uid)} characters")
                    return True
            elif keycode in KEY_MAP:
                uid_buffer.append(KEY_MAP[keycode])
                print(f"  Key: {KEY_MAP[keycode]}", end="", flush=True)

    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        try:
            rfid_dev.ungrab()
        except Exception:
            pass

    return False


if __name__ == "__main__":
    found = discover_devices()
    if found:
        success = test_rfid_read()
        sys.exit(0 if success else 1)
    else:
        sys.exit(1)
