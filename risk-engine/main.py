#!/usr/bin/env python3
"""
Risk Engine API
Aggregates events, calculates risk scores, generates alerts
"""

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from collections import defaultdict
import logging
import os
import json
import asyncio
import shutil
from pathlib import Path
from contextlib import asynccontextmanager

from models import *
from schemas import *
from auth import *

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
# Default to localhost for easier native (non-Docker) development on Windows.
# In Docker, this is overridden by the DATABASE_URL environment variable.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://riskuser:riskpass123@localhost:5432/risk_detection",
)
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Redis for caching and cooldowns
import redis.asyncio as redis
# Default to localhost for native development; Docker overrides via REDIS_URL.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = None


def utc_now_naive() -> datetime:
    """UTC now as naive datetime for DB columns without timezone."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def parse_timestamp_to_utc_naive(timestamp: str) -> datetime:
    """Parse ISO timestamp and normalize to UTC naive."""
    normalized = timestamp.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _decision_to_label(decision: str) -> Optional[int]:
    if decision == "false_positive":
        return 0
    if decision in {"confirmed", "escalated"}:
        return 1
    return None


def _extract_event_confidence(alert: Alert, event_type: str) -> Optional[float]:
    summary = alert.event_summary or []
    values: List[float] = []
    for item in summary:
        if not isinstance(item, dict):
            continue
        if item.get("type") != event_type:
            continue
        try:
            values.append(float(item.get("confidence", 0.0)))
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


# Event aggregation state
class RiskAggregator:
    """Aggregates risk events and generates alerts"""
    
    def __init__(self):
        self.event_buffer = defaultdict(list)
        self.cooldowns = {}
        self.config = {}
        
    async def load_config(self, db: AsyncSession):
        """Load system configuration"""
        result = await db.execute(select(SystemConfig))
        configs = result.scalars().all()
        
        for config in configs:
            try:
                if isinstance(config.value, str):
                    self.config[config.key] = float(config.value)
                else:
                    self.config[config.key] = config.value
            except:
                self.config[config.key] = config.value
        
        logger.info(f"Loaded config: {self.config}")
    
    async def process_events(
        self,
        camera_id: str,
        events: List[dict],
        db: AsyncSession,
        event_timestamp: Optional[datetime] = None,
    ):
        """Process incoming events and generate alerts if needed"""
        
        # Load configuration if not loaded
        if not self.config:
            await self.load_config(db)
        
        window_seconds = self.config.get('aggregation_window_seconds', 60)
        alert_threshold = self.config.get('risk_score_alert_threshold', 15.0)
        critical_threshold = self.config.get('risk_score_critical_threshold', 25.0)
        cooldown_seconds = self.config.get('cooldown_seconds', 180)
        
        # Add events to buffer
        current_time = event_timestamp or utc_now_naive()
        for event in events:
            self.event_buffer[camera_id].append({
                'event': event,
                'timestamp': current_time
            })
        
        # Clean old events from buffer
        cutoff_time = current_time - timedelta(seconds=window_seconds)
        self.event_buffer[camera_id] = [
            e for e in self.event_buffer[camera_id]
            if e['timestamp'] > cutoff_time
        ]
        
        # Check cooldown
        cooldown_key = f"alert_{camera_id}"
        if cooldown_key in self.cooldowns:
            if (current_time - self.cooldowns[cooldown_key]).total_seconds() < cooldown_seconds:
                logger.debug(f"Camera {camera_id} in cooldown")
                return
        
        # Calculate risk score
        risk_score = await self._calculate_risk_score(camera_id, db)
        
        # Generate alert if threshold exceeded
        if risk_score >= alert_threshold:
            logger.info(f"Generating alert for camera {camera_id}: score={risk_score}")
            
            severity = 'critical' if risk_score >= critical_threshold else 'high' if risk_score >= alert_threshold * 1.3 else 'medium'
            
            await self._create_alert(camera_id, risk_score, severity, db, current_time)
            
            # Set cooldown
            self.cooldowns[cooldown_key] = current_time
            
            # Clear buffer for this camera
            self.event_buffer[camera_id] = []
    
    async def _calculate_risk_score(self, camera_id: str, db: AsyncSession) -> float:
        """Calculate aggregated risk score"""
        
        # Load event type weights
        result = await db.execute(select(RiskEventType))
        event_types = {et.id: et for et in result.scalars().all()}
        
        score = 0.0
        events_in_window = self.event_buffer[camera_id]
        
        for item in events_in_window:
            event = item['event']
            event_type_id = event['type']
            
            if event_type_id in event_types:
                event_type = event_types[event_type_id]
                weight = event_type.base_weight
                confidence = event.get('confidence', 1.0)
                
                # Duration factor (if available)
                duration_factor = 1.0
                if 'duration' in event.get('meta_data', {}):
                    duration_factor = min(event['meta_data']['duration'] / 5.0, 2.0)
                
                score += weight * confidence * duration_factor
        
        return score
    
    async def _create_alert(
        self,
        camera_id: str,
        risk_score: float,
        severity: str,
        db: AsyncSession,
        alert_timestamp: datetime,
    ):
        """Create alert in database and trigger clip saving"""
        
        # Get camera
        result = await db.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one_or_none()
        
        if not camera:
            logger.error(f"Camera not found: {camera_id}")
            return
        
        # Collect event summary
        events_in_window = self.event_buffer[camera_id]
        event_summary = []
        involved_track_ids = set()
        
        for item in events_in_window:
            event = item['event']
            event_summary.append({
                'type': event['type'],
                'track_ids': event.get('track_ids', []),
                'confidence': event.get('confidence', 0.0),
                'meta_data': event.get('meta_data', {})
            })
            involved_track_ids.update(event.get('track_ids', []))
        
        # Create alert
        alert = Alert(
            camera_id=camera_id,
            timestamp=alert_timestamp,
            risk_score=risk_score,
            severity=severity,
            status='new',
            event_summary=event_summary
        )
        
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        
        logger.info(f"Created alert {alert.id} for camera {camera_id}")
        
        # Request clip from Clip Service
        await self._request_clip(alert.id, camera_id)
        
        return alert
    
    async def _request_clip(self, alert_id: str, camera_id: str):
        """Request clip from Clip Service"""
        import aiohttp
        
        clip_service_url = os.getenv('CLIP_SERVICE_URL', 'http://clip-service:8002')
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{clip_service_url}/api/clips/save",
                    json={
                        'alert_id': str(alert_id),
                        'camera_id': str(camera_id),
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Clip requested for alert {alert_id}")
                    else:
                        logger.error(f"Failed to request clip: {response.status}")
        except Exception as e:
            logger.error(f"Error requesting clip: {e}")


# Global aggregator instance
aggregator = RiskAggregator()


async def ensure_default_event_types():
    """
    Ensure missing event types exist in DB so analytics events become part of risk scoring.
    This is safe to run on every startup (idempotent per event type).
    """
    async with AsyncSessionLocal() as db:
        # Types for analytics_service extras
        default_types = [
            {
                "id": "VIOLENCE_POSE_RISK",
                "name": "Violence (Pose)",
                "description": "Violence classification based on pose keypoints over time.",
                "base_weight": 10.0,
                "config": {"violence_threshold": 0.7, "cooldown_sec": 10.0},
            },
            {
                "id": "PROFANITY_RISK",
                "name": "Profanity / Swear Words",
                "description": "Profanity keywords detected from OCR text stream.",
                "base_weight": 6.0,
                "config": {"event_cooldown_sec": 30.0, "min_keywords_found": 1},
            },
        ]

        for item in default_types:
            result = await db.execute(select(RiskEventType).where(RiskEventType.id == item["id"]))
            existing = result.scalar_one_or_none()
            if existing is None:
                db.add(
                    RiskEventType(
                        id=item["id"],
                        name=item["name"],
                        description=item["description"],
                        base_weight=float(item["base_weight"]),
                        enabled=True,
                        config=item["config"],
                    )
                )
            else:
                existing.name = item["name"]
                existing.description = item["description"]
                existing.base_weight = float(item["base_weight"])
                existing.enabled = True
                existing.config = item["config"]

        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global redis_client
    
    # Startup
    logger.info("Starting Risk Engine API")
    redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    
    # Auto-create admin user if not exists
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.username == 'admin'))
            admin_user = result.scalar_one_or_none()
            
            if not admin_user:
                logger.info("Admin user not found, creating...")
                import bcrypt
                password_hash = bcrypt.hashpw(b'admin123', bcrypt.gensalt(rounds=12)).decode('utf-8')
                
                admin = User(
                    username='admin',
                    password_hash=password_hash,
                    role='admin',
                    full_name='Administrator',
                    email='admin@school.com',
                    active=True
                )
                session.add(admin)
                await session.commit()
                logger.info("✅ Admin user created successfully! Username: admin, Password: admin123")
            else:
                logger.info(f"Admin user already exists (ID: {admin_user.id})")
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")

    # Ensure analytics-generated event types exist (so scoring works).
    try:
        await ensure_default_event_types()
    except Exception as e:
        logger.error(f"Failed to ensure default risk event types: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Risk Engine API")
    if redis_client:
        await redis_client.close()


# Create FastAPI app
app = FastAPI(
    title="School Risk Detection - Risk Engine API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency to get DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        if payload is None:
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if user is None or not user.active:
        raise credentials_exception
    
    return user


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "service": "risk-engine"}


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "redis": "connected" if redis_client else "disconnected"
    }


# ========== Authentication ==========

@app.post("/api/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login endpoint"""
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Update last login
    user.last_login = datetime.now()
    await db.commit()
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role
    }


@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return current_user


# ========== Events Endpoint ==========

@app.post("/api/events")
async def receive_events(
    event_data: EventData,
    db: AsyncSession = Depends(get_db)
):
    """Receive events from analytics service"""
    
    camera_id = event_data.camera_id
    events = event_data.events
    
    logger.info(f"Received {len(events)} events from camera {camera_id}")
    
    # Store raw events in database
    try:
        event_timestamp = parse_timestamp_to_utc_naive(event_data.timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format")

    for event in events:
        risk_event = RiskEvent(
            camera_id=camera_id,
            event_type=event['type'],
            timestamp=event_timestamp,
            confidence=event.get('confidence', 0.0),
            involved_track_ids=event.get('track_ids', []),
            meta_data=event.get('meta_data', {})
        )
        db.add(risk_event)
    
    await db.commit()
    
    # Process for aggregation and alerting
    if events:
        await aggregator.process_events(camera_id, events, db, event_timestamp)
    
    return {"status": "ok", "events_processed": len(events)}


# ========== Alerts Endpoints ==========

@app.get("/api/alerts", response_model=List[AlertResponse])
async def get_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    camera_id: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get alerts with filters"""
    
    query = select(Alert).options(selectinload(Alert.camera))
    
    if status:
        query = query.where(Alert.status == status)
    if severity:
        query = query.where(Alert.severity == severity)
    if camera_id:
        query = query.where(Alert.camera_id == camera_id)
    
    query = query.order_by(desc(Alert.timestamp)).limit(limit)
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    return alerts


@app.get("/api/alerts/{alert_id}", response_model=AlertDetailResponse)
async def get_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get alert details"""
    
    result = await db.execute(
        select(Alert)
        .where(Alert.id == alert_id)
        .options(
            selectinload(Alert.camera),
            selectinload(Alert.decisions)
        )
    )
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return alert


@app.post("/api/alerts/{alert_id}/decision")
async def create_alert_decision(
    alert_id: str,
    decision_data: AlertDecisionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Guard creates decision on alert"""
    
    # Get alert
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Create decision
    decision = AlertDecision(
        alert_id=alert_id,
        user_id=str(current_user.id),
        decision=decision_data.decision,
        comment=decision_data.comment
    )
    db.add(decision)
    
    # Update alert status
    status_map = {
        'confirmed': 'confirmed',
        'false_positive': 'false_positive',
        'escalated': 'escalated'
    }
    alert.status = status_map.get(decision_data.decision, 'closed')
    alert.updated_at = datetime.now()
    
    await db.commit()
    
    # Log audit
    audit_entry = AuditLog(
        user_id=str(current_user.id),
        action=f"alert_decision_{decision_data.decision}",
        resource_type="alert",
        resource_id=alert_id,
        details={"decision": decision_data.decision, "comment": decision_data.comment}
    )
    db.add(audit_entry)
    await db.commit()
    
    return {"status": "ok", "decision_id": str(decision.id)}


# ========== Retraining Endpoints ==========

@app.post("/api/retraining/dataset/export")
async def export_retraining_dataset(
    export_request: RetrainingDatasetExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export labeled alerts into a local dataset directory."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    output_dir = Path(os.getenv("RETRAINING_DATASET_PATH", "./retraining-data")).resolve()
    positive_dir = output_dir / "positive"
    negative_dir = output_dir / "negative"
    output_dir.mkdir(parents=True, exist_ok=True)
    positive_dir.mkdir(parents=True, exist_ok=True)
    negative_dir.mkdir(parents=True, exist_ok=True)

    result = await db.execute(
        select(Alert).options(selectinload(Alert.decisions)).order_by(desc(Alert.timestamp))
    )
    alerts = result.scalars().all()

    exported = 0
    skipped = 0
    manifest_path = output_dir / "manifest.jsonl"

    with manifest_path.open("w", encoding="utf-8") as manifest:
        for alert in alerts:
            if not alert.decisions:
                skipped += 1
                continue

            latest_decision = max(
                alert.decisions,
                key=lambda d: d.timestamp or datetime.min,
            )
            label = _decision_to_label(latest_decision.decision)
            if label is None:
                skipped += 1
                continue

            has_clip = bool(alert.clip_path and os.path.exists(alert.clip_path))
            if not has_clip and not export_request.include_without_clip:
                skipped += 1
                continue

            subset_dir = positive_dir if label == 1 else negative_dir
            clip_target = None
            if has_clip:
                src = Path(alert.clip_path)
                clip_target = subset_dir / f"{alert.id}{src.suffix.lower() or '.mp4'}"
                if src.resolve() != clip_target.resolve():
                    shutil.copy2(src, clip_target)

            row = {
                "alert_id": str(alert.id),
                "camera_id": str(alert.camera_id),
                "label": label,
                "decision": latest_decision.decision,
                "decision_comment": latest_decision.comment,
                "alert_timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
                "risk_score": alert.risk_score,
                "severity": alert.severity,
                "clip_path": str(clip_target) if clip_target else None,
                "event_summary": alert.event_summary or [],
            }
            manifest.write(json.dumps(row, ensure_ascii=False) + "\n")
            exported += 1

    return {
        "status": "ok",
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "exported": exported,
        "skipped": skipped,
    }


@app.post("/api/retraining/thresholds/recompute", response_model=RetrainingThresholdResult)
async def recompute_thresholds_from_feedback(
    request: RetrainingThresholdRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute recommended threshold from operator decisions."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    if request.min_samples < 4:
        raise HTTPException(status_code=400, detail="min_samples must be >= 4")

    result = await db.execute(
        select(Alert).options(selectinload(Alert.decisions)).order_by(desc(Alert.timestamp))
    )
    alerts = result.scalars().all()

    samples: List[dict] = []
    for alert in alerts:
        if not alert.decisions:
            continue
        latest_decision = max(alert.decisions, key=lambda d: d.timestamp or datetime.min)
        label = _decision_to_label(latest_decision.decision)
        if label is None:
            continue
        confidence = _extract_event_confidence(alert, request.event_type)
        if confidence is None:
            continue
        samples.append({"y": label, "score": confidence})

    total = len(samples)
    positives = sum(1 for s in samples if s["y"] == 1)
    negatives = total - positives
    if total < request.min_samples or positives == 0 or negatives == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Not enough labeled samples for {request.event_type}. "
                f"Need >= {request.min_samples} and both classes present."
            ),
        )

    best = {"thr": 0.85, "f1": -1.0, "precision": 0.0, "recall": 0.0}
    threshold = 0.0
    while threshold <= 1.000001:
        tp = fp = fn = 0
        for sample in samples:
            pred = 1 if sample["score"] >= threshold else 0
            if pred == 1 and sample["y"] == 1:
                tp += 1
            elif pred == 1 and sample["y"] == 0:
                fp += 1
            elif pred == 0 and sample["y"] == 1:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        if f1 > best["f1"] or (f1 == best["f1"] and threshold > best["thr"]):
            best = {"thr": round(threshold, 4), "f1": f1, "precision": precision, "recall": recall}
        threshold += request.step

    output_path = Path(
        os.getenv("RETRAINING_THRESHOLDS_PATH", "./retraining-data/threshold_overrides.json")
    ).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    existing[request.event_type] = {
        "threshold": best["thr"],
        "f1": round(best["f1"], 4),
        "precision": round(best["precision"], 4),
        "recall": round(best["recall"], 4),
        "samples_total": total,
        "positives": positives,
        "negatives": negatives,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    output_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    return RetrainingThresholdResult(
        event_type=request.event_type,
        threshold=float(best["thr"]),
        f1=float(round(best["f1"], 4)),
        precision=float(round(best["precision"], 4)),
        recall=float(round(best["recall"], 4)),
        samples_total=total,
        positives=positives,
        negatives=negatives,
        exported_at=utc_now_naive(),
        output_path=str(output_path),
    )


@app.get("/api/retraining/thresholds")
async def get_retraining_thresholds(
    current_user: User = Depends(get_current_user),
):
    """Return current threshold overrides file content."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    output_path = Path(
        os.getenv("RETRAINING_THRESHOLDS_PATH", "./retraining-data/threshold_overrides.json")
    ).resolve()
    if not output_path.exists():
        return {"status": "missing", "path": str(output_path), "thresholds": {}}
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="threshold overrides file is not valid JSON")
    return {"status": "ok", "path": str(output_path), "thresholds": payload}


# ========== Cameras Endpoints ==========

@app.get("/api/cameras", response_model=List[CameraResponse])
async def get_cameras(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all cameras"""
    
    result = await db.execute(select(Camera))
    cameras = result.scalars().all()
    
    return cameras


@app.post("/api/cameras")
async def create_camera(
    camera_data: CameraCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new camera (admin only)"""
    
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    camera = Camera(**camera_data.dict())
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    
    return camera


@app.put("/api/cameras/{camera_id}")
async def create_or_update_camera(
    camera_id: str,
    camera_data: CameraCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create or update camera (used by analytics service, no auth required)"""
    
    # Check if camera exists
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    
    if camera:
        # Update existing camera
        for key, value in camera_data.dict(exclude_unset=True).items():
            setattr(camera, key, value)
        camera.updated_at = datetime.now()
        camera.last_seen = datetime.now()
        # Fix: Set status to 'online' when analytics service updates camera
        camera.status = 'online'
    else:
        # Create new camera
        camera_dict = camera_data.dict()
        camera_dict['id'] = camera_id
        # Fix: Set initial status to 'online'
        camera_dict['status'] = 'online'
        camera = Camera(**camera_dict)
        db.add(camera)
    
    await db.commit()
    await db.refresh(camera)
    
    return camera


@app.get("/api/cameras/{camera_id}/stats")
async def get_camera_stats(
    camera_id: str,
    hours: int = 24,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get camera statistics"""
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    # Alert statistics
    result = await db.execute(
        select(
            func.count(Alert.id).label('total_alerts'),
            func.count(Alert.id).filter(Alert.severity == 'critical').label('critical_alerts'),
            func.avg(Alert.risk_score).label('avg_risk_score')
        )
        .where(and_(
            Alert.camera_id == camera_id,
            Alert.timestamp >= cutoff_time
        ))
    )
    stats = result.first()
    
    return {
        "camera_id": camera_id,
        "period_hours": hours,
        "total_alerts": stats.total_alerts or 0,
        "critical_alerts": stats.critical_alerts or 0,
        "avg_risk_score": float(stats.avg_risk_score) if stats.avg_risk_score else 0.0
    }


@app.post("/api/cameras/{camera_id}/heartbeat")
async def camera_heartbeat(
    camera_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Camera heartbeat - updates last_seen and status"""
    
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    
    if camera:
        camera.last_seen = datetime.now()
        camera.status = 'online'
        await db.commit()
        return {"status": "ok", "camera_id": camera_id}
    else:
        raise HTTPException(status_code=404, detail="Camera not found")


# ========== Configuration Endpoints ==========

@app.get("/api/config")
async def get_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get system configuration"""
    
    result = await db.execute(select(SystemConfig))
    configs = result.scalars().all()
    
    return {c.key: c.value for c in configs}


@app.put("/api/config/{key}")
async def update_config(
    key: str,
    value: ConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update configuration (admin only)"""
    
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration key not found")
    
    config.value = value.value
    config.updated_at = datetime.now()
    config.updated_by = str(current_user.id)
    
    await db.commit()
    
    # Reload aggregator config
    await aggregator.load_config(db)
    
    return {"status": "ok", "key": key, "value": value.value}


# ========== Dashboard Statistics ==========

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics"""
    
    # Active alerts
    result = await db.execute(
        select(func.count(Alert.id))
        .where(Alert.status.in_(['new', 'in_review']))
    )
    active_alerts = result.scalar()
    
    # Today's alerts
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(Alert.id))
        .where(Alert.timestamp >= today_start)
    )
    today_alerts = result.scalar()
    
    # Online cameras
    result = await db.execute(
        select(func.count(Camera.id))
        .where(Camera.status == 'online')
    )
    online_cameras = result.scalar()
    
    # Total cameras
    result = await db.execute(select(func.count(Camera.id)))
    total_cameras = result.scalar()
    
    return {
        "active_alerts": active_alerts,
        "today_alerts": today_alerts,
        "online_cameras": online_cameras,
        "total_cameras": total_cameras,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
