# WebQuanLi Protocol

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
