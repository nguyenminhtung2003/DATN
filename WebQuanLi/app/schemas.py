import re
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import AliasChoices, BaseModel, Field, field_validator


PLATE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 .-]{3,19}$", re.IGNORECASE)
DEVICE_RE = re.compile(r"^[A-Z0-9_.:-]{3,50}$", re.IGNORECASE)
RFID_RE = re.compile(r"^[A-Z0-9_.:-]{1,50}$", re.IGNORECASE)
PHONE_RE = re.compile(r"^\+?\d{8,15}$")
GENDER_VALUES = {"nam", "nu", "nữ", "khac", "khác", "male", "female", "other"}


def _strip_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _validate_pattern(value: Optional[str], pattern: re.Pattern, field_name: str) -> Optional[str]:
    value = _strip_optional(value)
    if value is None:
        return None
    if not pattern.fullmatch(value):
        raise ValueError(f"{field_name} khong hop le")
    return value


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenData(BaseModel):
    username: str
    role: str


class DriverCreate(BaseModel):
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    rfid_tag: str
    vehicle_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ten tai xe khong duoc rong")
        return value

    @field_validator("rfid_tag")
    @classmethod
    def validate_rfid(cls, value: str) -> str:
        return _validate_pattern(value, RFID_RE, "RFID")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        return _validate_pattern(value, PHONE_RE, "So dien thoai")

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: Optional[str]) -> Optional[str]:
        value = _strip_optional(value)
        if value is not None and value.lower() not in GENDER_VALUES:
            raise ValueError("Gioi tinh khong hop le")
        return value


class DriverUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    vehicle_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_optional_name(cls, value: Optional[str]) -> Optional[str]:
        value = _strip_optional(value)
        if value == "":
            raise ValueError("Ten tai xe khong duoc rong")
        return value

    @field_validator("phone")
    @classmethod
    def validate_optional_phone(cls, value: Optional[str]) -> Optional[str]:
        return _validate_pattern(value, PHONE_RE, "So dien thoai")

    @field_validator("gender")
    @classmethod
    def validate_optional_gender(cls, value: Optional[str]) -> Optional[str]:
        value = _strip_optional(value)
        if value is not None and value.lower() not in GENDER_VALUES:
            raise ValueError("Gioi tinh khong hop le")
        return value


class VehicleCreate(BaseModel):
    plate_number: str
    name: str
    device_id: Optional[str] = None
    manager_phone: Optional[str] = None

    @field_validator("plate_number")
    @classmethod
    def validate_plate(cls, value: str) -> str:
        return _validate_pattern(value, PLATE_RE, "Bien so")

    @field_validator("name")
    @classmethod
    def validate_vehicle_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ten xe khong duoc rong")
        return value

    @field_validator("device_id")
    @classmethod
    def validate_device_id(cls, value: Optional[str]) -> Optional[str]:
        return _validate_pattern(value, DEVICE_RE, "Device ID")

    @field_validator("manager_phone")
    @classmethod
    def validate_manager_phone(cls, value: Optional[str]) -> Optional[str]:
        return _validate_pattern(value, PHONE_RE, "So dien thoai")


class VehicleUpdate(BaseModel):
    name: Optional[str] = None
    manager_phone: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_optional_vehicle_name(cls, value: Optional[str]) -> Optional[str]:
        value = _strip_optional(value)
        if value == "":
            raise ValueError("Ten xe khong duoc rong")
        return value

    @field_validator("manager_phone")
    @classmethod
    def validate_optional_manager_phone(cls, value: Optional[str]) -> Optional[str]:
        return _validate_pattern(value, PHONE_RE, "So dien thoai")


class TestAlertRequest(BaseModel):
    level: int
    state: str  # "on" | "off"


class HardwareData(BaseModel):
    power: bool = False
    cellular: bool = False
    gps: bool = False
    camera: bool = False
    rfid: bool = False
    speaker: bool = False
    camera_ok: Optional[bool] = None
    rfid_reader_ok: Optional[bool] = None
    gps_uart_ok: Optional[bool] = None
    gps_fix_ok: Optional[bool] = None
    bluetooth_adapter_ok: Optional[bool] = None
    bluetooth_speaker_connected: Optional[bool] = None
    speaker_output_ok: Optional[bool] = None
    websocket_ok: Optional[bool] = None
    queue_pending: int = 0
    last_seen: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def _coalesce(explicit: Optional[bool], legacy: bool) -> bool:
        return bool(legacy if explicit is None else explicit)

    @property
    def power_effective(self) -> bool:
        return bool(self.power)

    @property
    def camera_effective(self) -> bool:
        return self._coalesce(self.camera_ok, self.camera)

    @property
    def rfid_effective(self) -> bool:
        return self._coalesce(self.rfid_reader_ok, self.rfid)

    @property
    def gps_effective(self) -> bool:
        return self._coalesce(self.gps_uart_ok, self.gps)

    @property
    def speaker_effective(self) -> bool:
        return self._coalesce(self.speaker_output_ok, self.speaker)

    @property
    def websocket_effective(self) -> bool:
        return self._coalesce(self.websocket_ok, self.cellular)


class GPSData(BaseModel):
    lat: float
    lng: float
    speed: Optional[float] = None
    heading: Optional[float] = None
    fix_ok: Optional[bool] = None
    timestamp: Optional[float] = None


class AlertData(BaseModel):
    level: str
    ear: Optional[float] = None
    mar: Optional[float] = None
    pitch: Optional[float] = None
    perclos: Optional[float] = None
    ai_state: Optional[str] = None
    ai_confidence: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("ai_confidence", "confidence"),
    )
    ai_reason: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ai_reason", "reason"),
    )
    lat: Optional[float] = None
    lng: Optional[float] = None
    speed: Optional[float] = None
    gps_fix_ok: Optional[bool] = None
    timestamp: Optional[float] = None


class FaceMismatchData(BaseModel):
    rfid_tag: str
    expected: str
    snapshot: Optional[str] = None
    timestamp: Optional[float] = None


class SessionStartData(BaseModel):
    rfid_tag: str
    driver_id: Optional[int] = None
    timestamp: Optional[float] = None


class SessionEndData(BaseModel):
    rfid_tag: str
    timestamp: Optional[float] = None


class AlertFilter(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    vehicle_id: Optional[int] = None
    driver_id: Optional[int] = None
    alert_type: Optional[str] = None


# --- WebSocket Contract Schemas ---

class DriverData(BaseModel):
    name: Optional[str] = None
    rfid: str = Field(validation_alias=AliasChoices("rfid", "rfid_tag"))


class VerifyErrorData(BaseModel):
    rfid_tag: str
    reason: Literal[
        "MISSING_VERIFIER",
        "LOW_CONFIDENCE",
        "NO_FACE_FRAME",
        "NO_ENROLLMENT",
        "UNKNOWN_ERROR",
        "MISMATCH",
    ]
    timestamp: Optional[float] = None


class VerifySnapshotData(BaseModel):
    rfid_tag: str
    status: Literal["DEMO_VERIFIED", "VERIFIED", "MISMATCH"]
    message: Optional[str] = None
    snapshot_path: Optional[str] = None
    timestamp: Optional[float] = None


class OTAStatusData(BaseModel):
    status: str  # "APPLIED", "FAILED", "DOWNLOADING"
    filename: Optional[str] = None
    progress: Optional[int] = 0
    error: Optional[str] = None


class WsCommandOut(BaseModel):
    action: Literal[
        "test_alert",
        "update_software",
        "sync_driver_registry",
        "connect_monitoring",
        "disconnect_monitoring",
    ]
    level: Optional[int] = None
    state: Optional[str] = None
    download_url: Optional[str] = None
    filename: Optional[str] = None
    manifest_url: Optional[str] = None
    checksum: Optional[str] = None
