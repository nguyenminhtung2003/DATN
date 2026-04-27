import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime,
    ForeignKey, Enum, Text,
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
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    drivers = relationship("Driver", back_populates="vehicle", lazy="selectin")
    hardware_statuses = relationship("HardwareStatus", back_populates="vehicle", lazy="selectin")
    sessions = relationship("DriverSession", back_populates="vehicle", lazy="selectin")
    alerts = relationship("SystemAlert", back_populates="vehicle", lazy="selectin")


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    phone = Column(String(15), nullable=True)
    rfid_tag = Column(String(50), unique=True, nullable=False, index=True)
    face_image_path = Column(String(255), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    vehicle = relationship("Vehicle", back_populates="drivers")
    sessions = relationship("DriverSession", back_populates="driver", lazy="selectin")


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
    session = relationship("DriverSession", back_populates="alerts")


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
