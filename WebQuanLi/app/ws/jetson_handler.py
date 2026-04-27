import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.event_bus import event_bus
from app.database import async_session_factory
from app.models import (
    Driver, DriverSession, HardwareStatus, SystemAlert,
    AlertType, AlertLevel, Vehicle,
)
from app.schemas import (
    HardwareData, SessionStartData, SessionEndData,
    AlertData, FaceMismatchData, OTAStatusData, GPSData,
    DriverData, VerifyErrorData, VerifySnapshotData, WsCommandOut
)
from pydantic import ValidationError
from app.services.sms_service import send_face_mismatch_sms
from app.services.jetson_session_service import (
    close_active_session,
    create_drowsiness_alert,
    resolve_driver_by_rfid,
    start_or_reuse_session,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections from Jetson devices."""

    def __init__(self):
        self.active: Dict[str, WebSocket] = {}
        self.last_seen: Dict[str, datetime] = {}

    async def connect(self, device_id: str, ws: WebSocket):
        await ws.accept()
        self.active[device_id] = ws
        self.last_seen[device_id] = datetime.now(timezone.utc)
        logger.info(f"Jetson connected: {device_id}")

    def disconnect(self, device_id: str):
        self.active.pop(device_id, None)
        offline_time = datetime.now(timezone.utc)
        self.last_seen[device_id] = offline_time
        logger.warning(f"Jetson disconnected: {device_id}")

    async def send_command(self, device_id: str, data: dict):
        ws = self.active.get(device_id)
        if ws:
            await ws.send_json(data)


manager = ConnectionManager()


def _map_alert_level(level_str: str) -> AlertLevel:
    mapping = {
        "WARNING": AlertLevel.LEVEL_1,
        "LEVEL_1": AlertLevel.LEVEL_1,
        "DANGER": AlertLevel.LEVEL_2,
        "LEVEL_2": AlertLevel.LEVEL_2,
        "CRITICAL": AlertLevel.LEVEL_3,
        "LEVEL_3": AlertLevel.LEVEL_3,
    }
    return mapping.get(level_str, AlertLevel.LEVEL_1)


async def _enrich_driver_payload(vehicle_id: int, payload: dict) -> dict:
    enriched = dict(payload)
    rfid = enriched.get("rfid") or enriched.get("rfid_tag")
    if not rfid:
        return enriched

    async with async_session_factory() as db:
        driver = await resolve_driver_by_rfid(db, rfid)
        if not driver or driver.vehicle_id not in (None, vehicle_id):
            return enriched

        if not enriched.get("name"):
            enriched["name"] = driver.name
        enriched["face_image_path"] = driver.face_image_path
        enriched["driver_face_image"] = driver.face_image_path
        enriched["driver_phone"] = driver.phone
        enriched["driver_age"] = driver.age
        enriched["driver_gender"] = driver.gender
    return enriched


@router.websocket("/ws/jetson/{device_id}")
async def jetson_websocket(ws: WebSocket, device_id: str):
    await manager.connect(device_id, ws)
    channel = f"vehicle:{device_id}"

    # --- Tối ưu: Cache thông tin xe ---
    vid = None
    manager_phone = None
    plate_number = None

    async with async_session_factory() as db:
        vehicle_result = await db.execute(
            select(Vehicle).where(Vehicle.device_id == device_id)
        )
        vehicle = vehicle_result.scalar_one_or_none()
        if vehicle:
            vid = vehicle.id
            manager_phone = vehicle.manager_phone
            plate_number = vehicle.plate_number

    if not vid:
        logger.warning(f"Jetson {device_id} kết nối nhưng thiết bị chưa được đăng ký trong DB!")
        await ws.close()
        manager.disconnect(device_id)
        return

    # Báo online cho Browser
    await event_bus.publish(channel, "connection", {"status": "online", "device_id": device_id})

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")
            payload = data.get("data", {})
            manager.last_seen[device_id] = datetime.now(timezone.utc)

            # Các msg tuần suất cao (như gps, ota) hoặc chẩn đoán (verify_error) chỉ nhảy qua event_bus mà không đụng Database
            if msg_type in ("driver", "gps", "ota_status", "verify_error", "verify_snapshot"):
                try:
                    if msg_type == "gps":
                        GPSData(**payload)
                    elif msg_type == "ota_status":
                        OTAStatusData(**payload)
                    elif msg_type == "driver":
                        DriverData(**payload)
                    elif msg_type == "verify_error":
                        VerifyErrorData(**payload)
                    elif msg_type == "verify_snapshot":
                        VerifySnapshotData(**payload)
                except ValidationError as e:
                    logger.error(f"Contract error ({msg_type}) from {device_id}: {e}")
                    continue

                publish_payload = payload
                if msg_type == "driver":
                    publish_payload = await _enrich_driver_payload(vid, payload)

                await event_bus.publish(channel, msg_type, publish_payload)
                continue

            # Các msg cần xử lý vào CSDL
            async with async_session_factory() as db:
                if msg_type == "hardware":
                    try:
                        hw_data = HardwareData(**payload)
                    except ValidationError as e:
                        logger.error(f"Contract error (hardware) from {device_id}: {e}")
                        continue

                    hw = HardwareStatus(
                        vehicle_id=vid,
                        power_ok=hw_data.power_effective,
                        cellular_ok=hw_data.websocket_effective,
                        gps_ok=hw_data.gps_effective,
                        camera_ok=hw_data.camera_effective,
                        rfid_ok=hw_data.rfid_effective,
                        speaker_ok=hw_data.speaker_effective,
                    )
                    db.add(hw)
                    await db.commit()
                    publish_payload = dict(payload)
                    publish_payload.update({
                        "power": hw_data.power_effective,
                        "cellular": hw_data.websocket_effective,
                        "gps": hw_data.gps_effective,
                        "camera": hw_data.camera_effective,
                        "rfid": hw_data.rfid_effective,
                        "speaker": hw_data.speaker_effective,
                        "camera_ok": hw_data.camera_effective,
                        "rfid_reader_ok": hw_data.rfid_effective,
                        "gps_uart_ok": hw_data.gps_effective,
                        "speaker_output_ok": hw_data.speaker_effective,
                        "websocket_ok": hw_data.websocket_effective,
                    })
                    await event_bus.publish(channel, "hardware", publish_payload)

                elif msg_type == "session_start":
                    try:
                        start_data = SessionStartData(**payload)
                    except ValidationError as e:
                        logger.error(f"Contract error (session_start) from {device_id}: {e}")
                        continue
                        
                    driver = await resolve_driver_by_rfid(db, start_data.rfid_tag)
                    if not driver:
                        await event_bus.publish(channel, "verify_error", {
                            "rfid_tag": start_data.rfid_tag,
                            "reason": "UNKNOWN_ERROR",
                        })
                        continue

                    session = await start_or_reuse_session(db, vid, driver.id, timestamp=start_data.timestamp)
                    await event_bus.publish(channel, "session_start", {
                        "session_id": session.id,
                        "driver_name": driver.name,
                        "driver_phone": driver.phone,
                        "driver_age": driver.age,
                        "driver_gender": driver.gender,
                        "driver_face_image": driver.face_image_path,
                        "rfid_tag": start_data.rfid_tag,
                        "checkin_at": session.checkin_at.isoformat(),
                    })

                elif msg_type == "session_end":
                    try:
                        end_data = SessionEndData(**payload)
                    except ValidationError as e:
                        logger.error(f"Contract error (session_end) from {device_id}: {e}")
                        continue

                    active_session = await close_active_session(db, vid, timestamp=end_data.timestamp)
                    if active_session:
                        await event_bus.publish(channel, "session_end", {
                            "session_id": active_session.id,
                            "checkout_at": active_session.checkout_at.isoformat(),
                        })

                elif msg_type == "alert":
                    try:
                        alert_data = AlertData(**payload)
                    except ValidationError as e:
                        logger.error(f"Contract error (alert) from {device_id}: {e}")
                        continue

                    level = _map_alert_level(alert_data.level)
                    # Tìm ca chạy xe đang active
                    alert = await create_drowsiness_alert(
                        db,
                        vehicle_id=vid,
                        level=level,
                        ear=alert_data.ear,
                        mar=alert_data.mar,
                        pitch=alert_data.pitch,
                        perclos=alert_data.perclos,
                        ai_state=alert_data.ai_state,
                        ai_confidence=alert_data.ai_confidence,
                        ai_reason=alert_data.ai_reason,
                        lat=alert_data.lat,
                        lng=alert_data.lng,
                        timestamp=alert_data.timestamp,
                    )
                    await event_bus.publish(channel, "alert", {
                        **payload,
                        "alert_type": "DROWSINESS",
                        "timestamp": alert.timestamp.isoformat(),
                    })

                elif msg_type == "face_mismatch":
                    try:
                        face_data = FaceMismatchData(**payload)
                    except ValidationError as e:
                        logger.error(f"Contract error (face_mismatch) from {device_id}: {e}")
                        continue

                    alert = SystemAlert(
                        vehicle_id=vid,
                        alert_type=AlertType.FACE_MISMATCH,
                        alert_level=AlertLevel.CRITICAL,
                        message=f"RFID {face_data.rfid_tag} - Khuôn mặt không khớp, dự kiến: {face_data.expected}",
                        timestamp=datetime.fromtimestamp(face_data.timestamp, tz=timezone.utc) if face_data.timestamp else datetime.now(timezone.utc),
                    )
                    db.add(alert)
                    await db.commit()
                    await event_bus.publish(channel, "face_mismatch", {
                        **payload,
                        "timestamp": alert.timestamp.isoformat(),
                    })
                    # Tin nhắn SMS dùng biến Cache
                    if manager_phone:
                        asyncio.create_task(
                            send_face_mismatch_sms(
                                manager_phone,
                                plate_number,
                                face_data.expected,
                            )
                        )

    except WebSocketDisconnect:
        manager.disconnect(device_id)
        await event_bus.publish(channel, "connection", {"status": "offline", "device_id": device_id})
    except Exception as e:
        logger.error(f"WebSocket error for {device_id}: {e}")
        manager.disconnect(device_id)
        await event_bus.publish(channel, "connection", {"status": "offline", "device_id": device_id})
