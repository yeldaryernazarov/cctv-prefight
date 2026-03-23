"""
Pydantic schemas for API requests and responses
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


# ========== Authentication Schemas ==========

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str
    role: str


class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None


# ========== User Schemas ==========

class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: str
    active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ========== Camera Schemas ==========

class CameraBase(BaseModel):
    name: str
    rtsp_url: str
    rtsp_substream_url: Optional[str] = None
    location: Optional[str] = None
    fps: int = 15
    resolution: Optional[str] = None


class CameraCreate(CameraBase):
    pass


class CameraResponse(CameraBase):
    id: str
    status: str
    created_at: datetime
    last_seen: Optional[datetime] = None
    meta_data: Dict[str, Any] = {}
    
    class Config:
        from_attributes = True


# ========== Zone Schemas ==========

class ZoneCreate(BaseModel):
    camera_id: str
    name: str
    polygon: List[Dict[str, float]]
    zone_type: Optional[str] = None
    schedule_profile: str = 'default'


class ZoneResponse(BaseModel):
    id: str
    camera_id: str
    name: str
    polygon: List[Dict[str, float]]
    zone_type: Optional[str]
    active: bool
    
    class Config:
        from_attributes = True


# ========== Event Schemas ==========

class EventData(BaseModel):
    camera_id: str
    timestamp: str
    frame_id: int
    fps: float
    people_count: int
    tracks: List[Dict[str, Any]]
    events: List[Dict[str, Any]]


class RiskEventResponse(BaseModel):
    id: str
    camera_id: str
    event_type: str
    timestamp: datetime
    confidence: float
    involved_track_ids: List[int]
    meta_data: Dict[str, Any]
    
    class Config:
        from_attributes = True


# ========== Alert Schemas ==========

class AlertResponse(BaseModel):
    id: str
    camera_id: str
    timestamp: datetime
    risk_score: float
    severity: str
    status: str
    clip_path: Optional[str]
    created_at: datetime
    camera: Optional[CameraResponse] = None
    
    class Config:
        from_attributes = True


class AlertDetailResponse(AlertResponse):
    event_summary: List[Dict[str, Any]]
    clip_start_time: Optional[datetime]
    clip_end_time: Optional[datetime]
    decisions: List['AlertDecisionResponse'] = []


class AlertDecisionCreate(BaseModel):
    decision: str  # 'confirmed', 'false_positive', 'escalated'
    comment: Optional[str] = None
    
    @validator('decision')
    def validate_decision(cls, v):
        allowed = ['confirmed', 'false_positive', 'escalated']
        if v not in allowed:
            raise ValueError(f"Decision must be one of: {', '.join(allowed)}")
        return v


class AlertDecisionResponse(BaseModel):
    id: str
    alert_id: str
    user_id: str
    decision: str
    comment: Optional[str]
    timestamp: datetime
    
    class Config:
        from_attributes = True


# ========== Configuration Schemas ==========

class ConfigUpdate(BaseModel):
    value: Any


class SystemConfigResponse(BaseModel):
    key: str
    value: Any
    description: Optional[str]
    updated_at: datetime


# ========== Dashboard Schemas ==========

class DashboardStats(BaseModel):
    active_alerts: int
    today_alerts: int
    online_cameras: int
    total_cameras: int
    timestamp: str


class CameraStatsResponse(BaseModel):
    camera_id: str
    period_hours: int
    total_alerts: int
    critical_alerts: int
    avg_risk_score: float


# Update forward references
AlertDetailResponse.model_rebuild()
