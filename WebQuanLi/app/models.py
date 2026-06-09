import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime,
    ForeignKey, Enum, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AlertType(str, enum.Enum):
    DROWSINESS = "DROWSINESS"
    FACE_MISMATCH = "FACE_MISMATCH"
    TEST = "TEST"


class AlertLevel(str, enum.Enum):
    LEVEL_1 = "LEVEL_1"
    LEVEL_2 = "LEVEL_2"
    LEVEL_3 = "LEVEL_3"
    CRITICAL = "CRITICAL"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    role = Column(String(20), default="viewer")
    created_at = Column(DateTime, default=utcnow)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    device_id = Column(String(50), unique=True, nullable=True)
    manager_phone = Column(String(15), nullable=True)
    assistant_driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    drivers = relationship("Driver", back_populates="vehicle", foreign_keys="Driver.vehicle_id", lazy="selectin")
    assistant_driver = relationship("Driver", foreign_keys=[assistant_driver_id], lazy="selectin")
    hardware_statuses = relationship("HardwareStatus", back_populates="vehicle", lazy="selectin")
    hardware_incidents = relationship("HardwareIncident", back_populates="vehicle")
    sessions = relationship("DriverSession", back_populates="vehicle", lazy="selectin")
    alerts = relationship("SystemAlert", back_populates="vehicle", lazy="selectin")


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    phone = Column(String(15), nullable=True)
    telegram_chat_id = Column(String(32), nullable=True)
    rfid_tag = Column(String(50), unique=True, nullable=False, index=True)
    face_image_path = Column(String(255), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    vehicle = relationship("Vehicle", back_populates="drivers", foreign_keys=[vehicle_id])
    sessions = relationship("DriverSession", back_populates="driver", lazy="selectin")
    penalties = relationship("DriverPenalty", back_populates="driver", lazy="selectin")
    safety_adjustments = relationship("DriverSafetyAdjustment", back_populates="driver", lazy="selectin")


class HardwareStatus(Base):
    __tablename__ = "hardware_statuses"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    power_ok = Column(Boolean, default=False)
    cellular_ok = Column(Boolean, default=False)
    gps_ok = Column(Boolean, default=False)
    camera_ok = Column(Boolean, default=False)
    rfid_ok = Column(Boolean, default=False)
    speaker_ok = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=utcnow)

    vehicle = relationship("Vehicle", back_populates="hardware_statuses")


class HardwareIncident(Base):
    __tablename__ = "hardware_incidents"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("driver_sessions.id"), nullable=True, index=True)
    device_key = Column(String(30), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="warning")
    reason = Column(Text, nullable=False)
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False, default="error")
    first_seen_at = Column(DateTime, nullable=False, default=utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)
    admin_telegram_status = Column(String(30), nullable=False, default="pending")
    driver_telegram_status = Column(String(30), nullable=False, default="pending")
    admin_telegram_error = Column(Text, nullable=True)
    driver_telegram_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    vehicle = relationship("Vehicle", back_populates="hardware_incidents")
    driver = relationship("Driver")
    session = relationship("DriverSession")


class DriverSession(Base):
    __tablename__ = "driver_sessions"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    checkin_at = Column(DateTime, default=utcnow)
    checkout_at = Column(DateTime, nullable=True)

    vehicle = relationship("Vehicle", back_populates="sessions")
    driver = relationship("Driver", back_populates="sessions")
    alerts = relationship("SystemAlert", back_populates="session", lazy="selectin")


class SystemAlert(Base):
    __tablename__ = "system_alerts"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("driver_sessions.id"), nullable=True)
    alert_type = Column(Enum(AlertType), nullable=False)
    alert_level = Column(Enum(AlertLevel), nullable=False)
    ear_value = Column(Float, nullable=True)
    mar_value = Column(Float, nullable=True)
    pitch_value = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    snapshot_path = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=utcnow)

    vehicle = relationship("Vehicle", back_populates="alerts")
    driver = relationship("Driver")
    session = relationship("DriverSession", back_populates="alerts")
    penalty = relationship("DriverPenalty", back_populates="alert", uselist=False, lazy="selectin")


class DriverPenalty(Base):
    __tablename__ = "driver_penalties"
    __table_args__ = (
        UniqueConstraint("alert_id", name="uq_driver_penalties_alert_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("system_alerts.id"), nullable=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    session_id = Column(Integer, ForeignKey("driver_sessions.id"), nullable=True)
    violation_time = Column(DateTime, nullable=False)
    reason = Column(Text, nullable=False)
    amount_vnd = Column(Integer, nullable=False, default=200000)
    driver_telegram_status = Column(String(30), nullable=False, default="pending")
    assistant_telegram_status = Column(String(30), nullable=False, default="pending")
    admin_telegram_status = Column(String(30), nullable=False, default="pending")
    driver_telegram_error = Column(Text, nullable=True)
    assistant_telegram_error = Column(Text, nullable=True)
    admin_telegram_error = Column(Text, nullable=True)
    review_status = Column(String(30), nullable=False, default="pending")
    admin_note = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(50), nullable=True)
    recommended_action = Column(String(50), nullable=False, default="penalty_only")
    created_at = Column(DateTime, default=utcnow)

    alert = relationship("SystemAlert", back_populates="penalty")
    vehicle = relationship("Vehicle")
    driver = relationship("Driver", back_populates="penalties")
    session = relationship("DriverSession")
    safety_adjustments = relationship("DriverSafetyAdjustment", back_populates="penalty", lazy="selectin")


class DriverSafetyAdjustment(Base):
    __tablename__ = "driver_safety_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    penalty_id = Column(Integer, ForeignKey("driver_penalties.id"), nullable=True, index=True)
    delta_points = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    source_type = Column(String(30), nullable=False, index=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    driver = relationship("Driver", back_populates="safety_adjustments")
    penalty = relationship("DriverPenalty", back_populates="safety_adjustments")


class OtaAuditLog(Base):
    __tablename__ = "ota_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    username = Column(String(50), nullable=True)
    filename = Column(String(255), nullable=False)
    checksum = Column(String(64), nullable=False)
    status = Column(String(30), nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    vehicle = relationship("Vehicle")
