"""
SQLAlchemy models for Risk Detection system
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    rtsp_url = Column(Text, nullable=False)
    rtsp_substream_url = Column(Text)
    location = Column(String(255))
    status = Column(String(50), default='offline')
    fps = Column(Integer, default=15)
    resolution = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen = Column(DateTime)
    meta_data = Column(JSONB, default={})
    
    # Relationships
    zones = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="camera")
    risk_events = relationship("RiskEvent", back_populates="camera")


class Zone(Base):
    __tablename__ = "zones"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    camera_id = Column(UUID(as_uuid=False), ForeignKey("cameras.id", ondelete="CASCADE"))
    name = Column(String(255), nullable=False)
    polygon = Column(JSONB, nullable=False)
    zone_type = Column(String(50))
    schedule_profile = Column(String(50), default='default')
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    meta_data = Column(JSONB, default={})
    
    # Relationships
    camera = relationship("Camera", back_populates="zones")


class RiskEventType(Base):
    __tablename__ = "risk_event_types"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    base_weight = Column(Float, default=1.0)
    enabled = Column(Boolean, default=True)
    config = Column(JSONB, default={})
    
    # Relationships
    events = relationship("RiskEvent", back_populates="event_type_rel")


class RiskEvent(Base):
    __tablename__ = "risk_events"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    camera_id = Column(UUID(as_uuid=False), ForeignKey("cameras.id", ondelete="CASCADE"))
    zone_id = Column(UUID(as_uuid=False), ForeignKey("zones.id", ondelete="SET NULL"))
    event_type = Column(String(50), ForeignKey("risk_event_types.id"))
    timestamp = Column(DateTime, nullable=False)
    confidence = Column(Float, default=0.0)
    duration_seconds = Column(Float)
    involved_track_ids = Column(ARRAY(Integer))
    meta_data = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    camera = relationship("Camera", back_populates="risk_events")
    event_type_rel = relationship("RiskEventType", back_populates="events")


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    camera_id = Column(UUID(as_uuid=False), ForeignKey("cameras.id", ondelete="CASCADE"))
    zone_id = Column(UUID(as_uuid=False), ForeignKey("zones.id", ondelete="SET NULL"))
    timestamp = Column(DateTime, nullable=False)
    risk_score = Column(Float, nullable=False)
    severity = Column(String(20), default='medium')
    status = Column(String(50), default='new')
    clip_path = Column(Text)
    clip_start_time = Column(DateTime)
    clip_end_time = Column(DateTime)
    event_summary = Column(JSONB, default=[])
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    camera = relationship("Camera", back_populates="alerts")
    decisions = relationship("AlertDecision", back_populates="alert", cascade="all, delete-orphan")


class AlertDecision(Base):
    __tablename__ = "alert_decisions"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    alert_id = Column(UUID(as_uuid=False), ForeignKey("alerts.id", ondelete="CASCADE"))
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    decision = Column(String(50), nullable=False)
    comment = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    alert = relationship("Alert", back_populates="decisions")
    user = relationship("User", back_populates="decisions")


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    username = Column(String(255), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)
    full_name = Column(String(255))
    email = Column(String(255))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    decisions = relationship("AlertDecision", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100))
    resource_id = Column(UUID(as_uuid=False))
    details = Column(JSONB, default={})
    ip_address = Column(INET)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class SystemConfig(Base):
    __tablename__ = "system_config"
    
    key = Column(String(255), primary_key=True)
    value = Column(JSONB, nullable=False)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"))


class CameraStats(Base):
    __tablename__ = "camera_stats"
    
    id = Column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    camera_id = Column(UUID(as_uuid=False), ForeignKey("cameras.id", ondelete="CASCADE"))
    timestamp = Column(DateTime, nullable=False)
    fps = Column(Float)
    dropped_frames = Column(Integer)
    people_count = Column(Integer)
    gpu_util_percent = Column(Float)
    latency_ms = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
