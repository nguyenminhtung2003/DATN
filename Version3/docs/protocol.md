# WebQuanLi Protocol

Version3 sends JSON messages through the WebSocket queue as:

```json
{"type": "message_type", "data": {}}
```

Existing fields and message types are stable. New fields must be optional and
backward compatible so older WebQuanLi dashboards can ignore them safely.

## Hardware Message

Version3 sends a `hardware` message to WebQuanLi every `HW_REPORT_INTERVAL` seconds.

```json
{
  "type": "hardware",
  "data": {
    "camera_ok": true,
    "rfid_reader_ok": true,
    "gps_uart_ok": true,
    "gps_fix_ok": false,
    "bluetooth_adapter_ok": true,
    "bluetooth_speaker_connected": false,
    "speaker_output_ok": true,
    "websocket_ok": true,
    "queue_pending": 0,
    "timestamp": "2026-04-25T23:15:47+0700",
    "details": {
      "gps_reason": "NMEA_NO_FIX",
      "gps_last_sentence": "$GPGLL,,,,,,",
      "rfid_reason": "OPEN_OK",
      "rfid_device_path": "/dev/input/by-id/usb-IC_Reader_IC_Reader_08FF20171101-event-kbd",
      "bluetooth_speaker_mac": "7C:E9:13:33:93:BE",
      "bluetooth_speaker_name": null
    }
  }
}
```

Legacy fields remain present for older dashboard code: `camera`, `rfid`, `gps`, `speaker`,
`cellular`, `bluetooth`, and `bluetooth_adapter`.

## Alert Message

Version3 sends an `alert` message when the alert level changes.

```json
{
  "type": "alert",
  "data": {
    "level": "DANGER",
    "ear": 0.2,
    "mar": 0.4,
    "pitch": -12.0,
    "perclos": 0.5,
    "ai_state": "DROWSY",
    "ai_confidence": 0.9,
    "ai_reason": "Eyes closed for 1.8s",
    "timestamp": 1710000000.0
  }
}
```

Allowed level names remain `WARNING`, `DANGER`, and `CRITICAL` with legacy
`LEVEL_1`, `LEVEL_2`, and `LEVEL_3` accepted by WebQuanLi.

## Driver Verification Messages

Successful or explicit verification states use `verify_snapshot`.

```json
{
  "type": "verify_snapshot",
  "data": {
    "rfid_tag": "UID-123",
    "status": "VERIFIED",
    "message": "Face verification matched registered driver",
    "snapshot_path": null,
    "timestamp": 1710000000.0
  }
}
```

Failure and fail-safe states use `verify_error`.

```json
{
  "type": "verify_error",
  "data": {
    "rfid_tag": "UID-123",
    "reason": "NO_ENROLLMENT",
    "timestamp": 1710000000.0
  }
}
```

Current `verify_snapshot.status` values are `VERIFIED`, `DEMO_VERIFIED`, and
`MISMATCH`. Current `verify_error.reason` values include `MISSING_VERIFIER`,
`LOW_CONFIDENCE`, `NO_FACE_FRAME`, `NO_ENROLLMENT`, `UNKNOWN_ERROR`, and
`MISMATCH`.

## Session Messages

Version3 sends `session_start` after a driver is allowed to enter RUNNING.

```json
{
  "type": "session_start",
  "data": {
    "rfid_tag": "UID-123",
    "driver_id": null,
    "timestamp": 1710000000.0
  }
}
```

Version3 sends `session_end` when the active driving session ends.

```json
{
  "type": "session_end",
  "data": {
    "rfid_tag": "UID-123",
    "timestamp": 1710000300.0
  }
}
```

## Reference Image Source Policy

Primary verification reference images should come from the Jetson IR camera
capture path used during live verification. WebQuanLi/RGB image sync is allowed
as a fallback only unless metadata proves Jetson IR origin.

Driver registry entries use:

```json
{
  "rfid_tag": "UID-123",
  "local_reference_path": "storage/driver_faces/UID-123/reference.jpg",
  "reference_source": "jetson_ir",
  "reference_role": "primary"
}
```

Local Jetson enrollment records `reference_source=jetson_ir` and
`reference_role=primary`. WebQuanLi sync defaults to
`reference_source=webquanli_sync` and `reference_role=fallback` unless the
manifest explicitly supplies trusted Jetson IR metadata.

Existing verify payloads do not change because this metadata is local registry
state, not a WebSocket requirement.

## Status Rules

- `camera_ok` is true only when the camera capture loop is alive.
- `rfid_reader_ok` is true only when the USB HID reader is open.
- `gps_uart_ok` is true when the GPS UART opens and NMEA is observed.
- `gps_fix_ok` is true only when RMC/GGA reports a valid fix.
- `bluetooth_speaker_connected` is true only when BlueZ, `hcitool`, or PulseAudio confirms an active speaker connection.
- `speaker_output_ok` is true when the configured audio output backend is available.
- `websocket_ok` is true when Version3 is connected to WebQuanLi.

## Commands From WebQuanLi

```json
{"action": "connect_monitoring"}
{"action": "disconnect_monitoring"}
{"action": "test_alert", "level": 1, "state": "on"}
```

`connect_monitoring` and `disconnect_monitoring` only control monitoring/session behavior.
Hardware heartbeat stays enabled in both states.
