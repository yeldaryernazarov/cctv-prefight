#!/usr/bin/env python3
"""
Clip Service
Manages ring buffers and saves event clips
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio
import cv2
import os
import logging
from pathlib import Path
from collections import deque
import numpy as np
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database
# Default to localhost for native (non-Docker) Windows development.
# In Docker, this is overridden via the DATABASE_URL environment variable.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://riskuser:riskpass123@localhost:5432/risk_detection",
)
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Storage configuration
STORAGE_PATH = os.getenv("STORAGE_PATH", "/app/clips")
RING_BUFFER_SECONDS = int(os.getenv("RING_BUFFER_SECONDS", "60"))
CLIP_PRE_SECONDS = int(os.getenv("CLIP_PRE_SECONDS", "10"))
CLIP_POST_SECONDS = int(os.getenv("CLIP_POST_SECONDS", "10"))

# Ensure storage directories exist
Path(STORAGE_PATH).mkdir(parents=True, exist_ok=True)
Path("/app/buffers").mkdir(parents=True, exist_ok=True)


class ClipRequest(BaseModel):
    alert_id: str
    camera_id: str
    timestamp: str


class RingBuffer:
    """Ring buffer for storing recent frames"""
    
    def __init__(self, camera_id: str, max_seconds: int = 60, fps: int = 15):
        self.camera_id = camera_id
        self.max_frames = max_seconds * fps
        self.fps = fps
        self.frames = deque(maxlen=self.max_frames)
        self.timestamps = deque(maxlen=self.max_frames)
        self.rtsp_url = None
        self.cap = None
        self.running = False
        
    def add_frame(self, frame: np.ndarray, timestamp: datetime):
        """Add frame to buffer"""
        self.frames.append(frame.copy())
        self.timestamps.append(timestamp)
    
    def get_frames_around_time(self, target_time: datetime, pre_seconds: int, post_seconds: int):
        """Get frames around a specific time"""
        if not self.timestamps:
            return []
        
        start_time = target_time - timedelta(seconds=pre_seconds)
        end_time = target_time + timedelta(seconds=post_seconds)
        
        result_frames = []
        for frame, ts in zip(self.frames, self.timestamps):
            if start_time <= ts <= end_time:
                result_frames.append((frame, ts))
        
        return result_frames
    
    async def connect(self, rtsp_url: str):
        """Connect to RTSP stream"""
        self.rtsp_url = rtsp_url
        self.cap = cv2.VideoCapture(rtsp_url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not self.cap.isOpened():
            logger.error(f"Failed to open RTSP stream: {rtsp_url}")
            return False
        
        logger.info(f"Connected to camera {self.camera_id}")
        return True
    
    async def run(self):
        """Main loop to capture frames"""
        self.running = True
        
        while self.running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    # Try to reconnect
                    if self.rtsp_url:
                        await self.connect(self.rtsp_url)
                    await asyncio.sleep(5)
                    continue
                
                ret, frame = self.cap.read()
                if ret:
                    self.add_frame(frame, datetime.now())
                else:
                    logger.warning(f"Failed to read frame from camera {self.camera_id}")
                    await asyncio.sleep(1)
                
                await asyncio.sleep(1 / self.fps)
                
            except Exception as e:
                logger.error(f"Error in ring buffer for camera {self.camera_id}: {e}")
                await asyncio.sleep(5)
    
    def stop(self):
        """Stop capturing"""
        self.running = False
        if self.cap:
            self.cap.release()


class ClipManager:
    """Manages ring buffers and clip saving"""
    
    def __init__(self):
        self.buffers: Dict[str, RingBuffer] = {}
        self.buffer_tasks: Dict[str, asyncio.Task] = {}
    
    async def add_camera(self, camera_id: str, rtsp_url: str, fps: int = 15):
        """Add camera to monitoring"""
        if camera_id in self.buffers:
            logger.warning(f"Camera {camera_id} already being monitored")
            return
        
        buffer = RingBuffer(camera_id, RING_BUFFER_SECONDS, fps)
        await buffer.connect(rtsp_url)
        
        self.buffers[camera_id] = buffer
        task = asyncio.create_task(buffer.run())
        self.buffer_tasks[camera_id] = task
        
        logger.info(f"Started monitoring camera {camera_id}")
    
    async def remove_camera(self, camera_id: str):
        """Remove camera from monitoring"""
        if camera_id in self.buffers:
            self.buffers[camera_id].stop()
            if camera_id in self.buffer_tasks:
                self.buffer_tasks[camera_id].cancel()
                del self.buffer_tasks[camera_id]
            del self.buffers[camera_id]
            logger.info(f"Stopped monitoring camera {camera_id}")
    
    async def save_clip(
        self,
        alert_id: str,
        camera_id: str,
        timestamp: datetime,
        pre_seconds: int = CLIP_PRE_SECONDS,
        post_seconds: int = CLIP_POST_SECONDS
    ) -> Optional[str]:
        """Save clip around event time"""
        
        if camera_id not in self.buffers:
            logger.error(f"Camera {camera_id} not being monitored")
            return None
        
        buffer = self.buffers[camera_id]
        frames = buffer.get_frames_around_time(timestamp, pre_seconds, post_seconds)
        
        if not frames:
            logger.warning(f"No frames found for alert {alert_id}")
            return None
        
        # Create clip filename
        clip_filename = f"{alert_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.mp4"
        clip_path = os.path.join(STORAGE_PATH, clip_filename)
        
        # Save frames as video
        try:
            if frames:
                height, width = frames[0][0].shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(clip_path, fourcc, buffer.fps, (width, height))
                
                for frame, _ in frames:
                    out.write(frame)
                
                out.release()
                
                logger.info(f"Saved clip: {clip_path} ({len(frames)} frames)")
                return clip_path
        except Exception as e:
            logger.error(f"Error saving clip: {e}")
            return None
        
        return None


# Global clip manager
clip_manager = ClipManager()


# FastAPI app
app = FastAPI(title="Clip Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@app.on_event("startup")
async def startup_event():
    """Initialize clip manager with existing cameras"""
    logger.info("Starting Clip Service")
    
    # Load cameras from database
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        result = await db.execute(
            text("SELECT id, name, rtsp_substream_url, rtsp_url, fps FROM cameras WHERE status = 'online'")
        )
        cameras = result.fetchall()
        
        for camera in cameras:
            camera_id, name, substream_url, main_url, fps = camera
            rtsp_url = substream_url or main_url
            if rtsp_url:
                await clip_manager.add_camera(str(camera_id), rtsp_url, fps or 15)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Clip Service")
    for camera_id in list(clip_manager.buffers.keys()):
        await clip_manager.remove_camera(camera_id)


@app.get("/")
async def root():
    return {"status": "ok", "service": "clip-service"}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "active_buffers": len(clip_manager.buffers),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/clips/save")
async def save_clip(clip_request: ClipRequest):
    """Save clip for an alert"""
    
    logger.info(f"Received clip save request for alert {clip_request.alert_id}")
    
    try:
        timestamp = datetime.fromisoformat(clip_request.timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format")
    
    # Save clip
    clip_path = await clip_manager.save_clip(
        clip_request.alert_id,
        clip_request.camera_id,
        timestamp
    )
    
    if not clip_path:
        raise HTTPException(status_code=500, detail="Failed to save clip")
    
    # Update alert in database
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        await db.execute(
            text("""
                UPDATE alerts 
                SET clip_path = :clip_path,
                    clip_start_time = :start_time,
                    clip_end_time = :end_time
                WHERE id = :alert_id
            """),
            {
                "clip_path": clip_path,
                "start_time": timestamp - timedelta(seconds=CLIP_PRE_SECONDS),
                "end_time": timestamp + timedelta(seconds=CLIP_POST_SECONDS),
                "alert_id": clip_request.alert_id
            }
        )
        await db.commit()
    
    return {
        "status": "ok",
        "clip_path": clip_path,
        "alert_id": clip_request.alert_id
    }


@app.get("/api/clips/{alert_id}")
async def get_clip(alert_id: str):
    """Get clip file for an alert"""
    
    # Get clip path from database
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        result = await db.execute(
            text("SELECT clip_path FROM alerts WHERE id = :alert_id"),
            {"alert_id": alert_id}
        )
        row = result.fetchone()
        
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Clip not found")
        
        clip_path = row[0]
    
    if not os.path.exists(clip_path):
        raise HTTPException(status_code=404, detail="Clip file not found on disk")
    
    return FileResponse(
        clip_path,
        media_type="video/mp4",
        filename=os.path.basename(clip_path)
    )


@app.post("/api/clips/camera/start")
async def start_camera_monitoring(camera_id: str, rtsp_url: str, fps: int = 15):
    """Start monitoring a camera"""
    await clip_manager.add_camera(camera_id, rtsp_url, fps)
    return {"status": "ok", "camera_id": camera_id}


@app.post("/api/clips/camera/stop")
async def stop_camera_monitoring(camera_id: str):
    """Stop monitoring a camera"""
    await clip_manager.remove_camera(camera_id)
    return {"status": "ok", "camera_id": camera_id}


@app.get("/api/clips/buffers")
async def list_buffers():
    """List active ring buffers"""
    buffers_info = []
    for camera_id, buffer in clip_manager.buffers.items():
        buffers_info.append({
            "camera_id": camera_id,
            "frame_count": len(buffer.frames),
            "running": buffer.running,
            "fps": buffer.fps
        })
    return {"buffers": buffers_info}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
