#!/usr/bin/env python3
"""
DeepStream Analytics Service
Handles RTSP streams, people detection, multi-object tracking, and risk event detection
"""

import sys
import cv2
import numpy as np
import time
import json
import asyncio
import aiohttp
from datetime import datetime
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional
import logging
import os
import yaml

# Optional advanced detectors
from pose_violence_detector import PoseViolenceDetector
from profanity_detector import ProfanityDetector

# Simple tracker implementation (ByteTrack-inspired)
from scipy.optimize import linear_sum_assignment
from filterpy.kalman import KalmanFilter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Single person detection"""
    bbox: List[float]  # [x1, y1, x2, y2]
    confidence: float
    frame_id: int
    timestamp: float


@dataclass
class Track:
    """Tracked person over time"""
    track_id: int
    bbox: List[float]
    confidence: float
    age: int
    hits: int
    time_since_update: int
    history: deque  # Position history
    velocity: Tuple[float, float]
    acceleration: Tuple[float, float]


class SimpleTracker:
    """Multi-object tracker using Kalman filter and Hungarian algorithm"""
    
    def __init__(self, max_age=30, min_hits=3, iou_threshold=0.3):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.tracks: List[Track] = []
        self.next_id = 1
        
    def _iou(self, bbox1, bbox2):
        """Calculate IoU between two bboxes"""
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        inter_area = max(0, x2 - x1) * max(0, y2 - y1)
        bbox1_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        bbox2_area = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        
        union_area = bbox1_area + bbox2_area - inter_area
        return inter_area / union_area if union_area > 0 else 0
    
    def _get_center(self, bbox):
        """Get center point of bbox"""
        return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    
    def _calculate_velocity(self, history):
        """Calculate velocity from position history"""
        if len(history) < 2:
            return (0.0, 0.0)
        
        p1 = history[-2]
        p2 = history[-1]
        return (p2[0] - p1[0], p2[1] - p1[1])
    
    def _calculate_acceleration(self, history):
        """Calculate acceleration from position history"""
        if len(history) < 3:
            return (0.0, 0.0)
        
        v1_x = history[-2][0] - history[-3][0]
        v1_y = history[-2][1] - history[-3][1]
        v2_x = history[-1][0] - history[-2][0]
        v2_y = history[-1][1] - history[-2][1]
        
        return (v2_x - v1_x, v2_y - v1_y)
    
    def update(self, detections: List[Detection]) -> List[Track]:
        """Update tracks with new detections"""
        
        # Predict new locations for existing tracks
        for track in self.tracks:
            track.time_since_update += 1
        
        # Match detections to tracks
        if len(self.tracks) > 0 and len(detections) > 0:
            iou_matrix = np.zeros((len(detections), len(self.tracks)))
            
            for d, det in enumerate(detections):
                for t, track in enumerate(self.tracks):
                    iou_matrix[d, t] = self._iou(det.bbox, track.bbox)
            
            # Hungarian algorithm for assignment
            det_indices, track_indices = linear_sum_assignment(-iou_matrix)
            
            matched_detections = set()
            matched_tracks = set()
            
            for d, t in zip(det_indices, track_indices):
                if iou_matrix[d, t] >= self.iou_threshold:
                    # Update matched track
                    track = self.tracks[t]
                    det = detections[d]
                    
                    track.bbox = det.bbox
                    track.confidence = det.confidence
                    track.time_since_update = 0
                    track.hits += 1
                    
                    center = self._get_center(det.bbox)
                    track.history.append(center)
                    track.velocity = self._calculate_velocity(track.history)
                    track.acceleration = self._calculate_acceleration(track.history)
                    
                    matched_detections.add(d)
                    matched_tracks.add(t)
        else:
            matched_detections = set()
            matched_tracks = set()
        
        # Create new tracks for unmatched detections
        for d, det in enumerate(detections):
            if d not in matched_detections:
                center = self._get_center(det.bbox)
                history = deque(maxlen=30)
                history.append(center)
                
                new_track = Track(
                    track_id=self.next_id,
                    bbox=det.bbox,
                    confidence=det.confidence,
                    age=1,
                    hits=1,
                    time_since_update=0,
                    history=history,
                    velocity=(0.0, 0.0),
                    acceleration=(0.0, 0.0)
                )
                self.tracks.append(new_track)
                self.next_id += 1
        
        # Remove old tracks
        self.tracks = [
            t for t in self.tracks 
            if t.time_since_update < self.max_age
        ]
        
        # Increment age for all tracks
        for track in self.tracks:
            track.age += 1
        
        # Return confirmed tracks only
        return [t for t in self.tracks if t.hits >= self.min_hits]


class RiskEventDetector:
    """Detects risk events from tracks"""
    
    def __init__(self, config: dict):
        self.config = config
        self.event_history = defaultdict(list)
        
    def _normalize_distance(self, dist_pixels, avg_height):
        """Normalize distance by average person height"""
        if avg_height == 0:
            return dist_pixels
        return dist_pixels / avg_height
    
    def detect_proximity_risk(self, tracks: List[Track], frame_width, frame_height) -> List[dict]:
        """Detect close proximity or rapid approach between people"""
        events = []
        config = self.config.get('PROXIMITY_RISK', {})
        
        distance_threshold = config.get('distance_threshold', 1.5)
        duration_min = config.get('duration_min_sec', 2)
        rapid_approach_percent = config.get('rapid_approach_percent', 50)
        
        for i, track1 in enumerate(tracks):
            for track2 in tracks[i+1:]:
                # Calculate current distance
                center1 = self._get_track_center(track1)
                center2 = self._get_track_center(track2)
                
                distance = np.linalg.norm(np.array(center1) - np.array(center2))
                
                # Normalize by average height
                avg_height = (self._get_bbox_height(track1.bbox) + 
                             self._get_bbox_height(track2.bbox)) / 2
                normalized_distance = self._normalize_distance(distance, avg_height)
                
                # Check if too close
                if normalized_distance < distance_threshold:
                    # Check duration
                    key = tuple(sorted([track1.track_id, track2.track_id]))
                    self.event_history[f'proximity_{key}'].append(time.time())
                    
                    # Clean old events
                    cutoff = time.time() - duration_min
                    self.event_history[f'proximity_{key}'] = [
                        t for t in self.event_history[f'proximity_{key}'] if t > cutoff
                    ]
                    
                    if len(self.event_history[f'proximity_{key}']) >= duration_min * 15:  # Assuming 15 FPS
                        events.append({
                            'type': 'PROXIMITY_RISK',
                            'track_ids': [track1.track_id, track2.track_id],
                            'confidence': min(track1.confidence, track2.confidence),
                            'meta_data': {
                                'normalized_distance': normalized_distance,
                                'centers': [center1, center2]
                            }
                        })
        
        return events
    
    def detect_crowd_risk(self, tracks: List[Track], zones: List[dict]) -> List[dict]:
        """Detect crowd formation or high density"""
        events = []
        config = self.config.get('CROWD_RISK', {})
        
        min_count = config.get('min_count', 5)
        density_threshold = config.get('density_threshold', 0.3)
        
        for zone in zones:
            tracks_in_zone = [
                t for t in tracks 
                if self._track_in_zone(t, zone['polygon'])
            ]
            
            if len(tracks_in_zone) >= min_count:
                # Calculate density
                zone_area = self._calculate_polygon_area(zone['polygon'])
                density = len(tracks_in_zone) / zone_area if zone_area > 0 else 0
                
                if density > density_threshold:
                    events.append({
                        'type': 'CROWD_RISK',
                        'track_ids': [t.track_id for t in tracks_in_zone],
                        'confidence': 0.8,
                        'zone_id': zone.get('id'),
                        'meta_data': {
                            'count': len(tracks_in_zone),
                            'density': density,
                            'zone_name': zone.get('name')
                        }
                    })
        
        return events
    
    def detect_kinetic_risk(self, tracks: List[Track]) -> List[dict]:
        """Detect high kinetic activity (rapid acceleration)"""
        events = []
        config = self.config.get('KINETIC_RISK', {})
        
        acceleration_threshold = config.get('acceleration_threshold', 5.0)
        duration_min = config.get('duration_min_sec', 1.5)
        
        for track in tracks:
            if len(track.history) < 3:
                continue
            
            # Calculate acceleration magnitude
            acc_magnitude = np.linalg.norm(track.acceleration)
            
            if acc_magnitude > acceleration_threshold:
                # Track duration of high acceleration
                key = f'kinetic_{track.track_id}'
                self.event_history[key].append(time.time())
                
                # Clean old events
                cutoff = time.time() - duration_min
                self.event_history[key] = [
                    t for t in self.event_history[key] if t > cutoff
                ]
                
                if len(self.event_history[key]) >= duration_min * 15:  # Assuming 15 FPS
                    events.append({
                        'type': 'KINETIC_RISK',
                        'track_ids': [track.track_id],
                        'confidence': track.confidence,
                        'meta_data': {
                            'acceleration': acc_magnitude,
                            'velocity': track.velocity
                        }
                    })
        
        return events
    
    def _get_track_center(self, track):
        """Get center of track bbox"""
        bbox = track.bbox
        return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    
    def _get_bbox_height(self, bbox):
        """Get height of bbox"""
        return bbox[3] - bbox[1]
    
    def _track_in_zone(self, track, polygon):
        """Check if track center is inside polygon zone"""
        center = self._get_track_center(track)
        return self._point_in_polygon(center, polygon)
    
    def _point_in_polygon(self, point, polygon):
        """Ray casting algorithm for point in polygon"""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]['x'], polygon[0]['y']
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]['x'], polygon[i % n]['y']
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def _calculate_polygon_area(self, polygon):
        """Calculate area of polygon using shoelace formula"""
        n = len(polygon)
        if n < 3:
            return 0
        
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += polygon[i]['x'] * polygon[j]['y']
            area -= polygon[j]['x'] * polygon[i]['y']
        
        return abs(area) / 2


class CameraProcessor:
    """Processes single camera stream"""
    
    def __init__(self, camera_config: dict, risk_detector: RiskEventDetector, system_config: dict):
        self.camera_id = camera_config['id']
        self.camera_name = camera_config['name']
        self.rtsp_url = camera_config.get('rtsp_substream_url') or camera_config['rtsp_url']
        self.zones = camera_config.get('zones', [])
        
        self.system_config = system_config or {}

        self.tracker = SimpleTracker()
        self.risk_detector = risk_detector
        
        self.cap = None
        self.frame_count = 0
        self.fps = 0
        self.last_fps_update = time.time()
        
        # --- Models: person detection + optional violence/profanity detectors ---
        models_dir = os.getenv(
            "MODELS_DIR",
            os.path.join(os.path.dirname(__file__), "models"),
        )
        models_cfg = self.system_config.get("models", {}) or {}
        person_cfg = self.system_config.get("person_detection", {}) or {}
        violence_cfg = self.system_config.get("violence_detection", {}) or {}
        profanity_cfg = self.system_config.get("profanity_detection", {}) or {}

        self.person_class_ids = person_cfg.get("class_ids", [0])
        self.person_conf = float(person_cfg.get("conf", 0.3))

        # YOLO model for person detection (GPU-accelerated when available)
        try:
            import torch
            from ultralytics import YOLO

            # Allow overriding device via env, but prefer CUDA when available
            requested_device = os.getenv("ANALYTICS_DEVICE", "cuda").lower()
            if requested_device == "cuda" and not torch.cuda.is_available():
                logger.warning(
                    "ANALYTICS_DEVICE=cuda requested, but CUDA is not available. "
                    "Falling back to CPU. Install GPU-enabled PyTorch to use CUDA."
                )
                requested_device = "cpu"

            self.device = requested_device

            # Allow users to "just drop" models into deepstream-analytics/models/.
            person_model_path = models_cfg.get("person_yolo_path")
            if not person_model_path:
                for cand in ["person_yolo.pt", "person_yolo_yolov8n.pt", "yolov8n.pt"]:
                    p = os.path.join(models_dir, cand)
                    if os.path.exists(p):
                        person_model_path = p
                        break

            if not person_model_path:
                # Last resort: download by name (may require internet).
                person_model_path = models_cfg.get("person_yolo_default", "yolov8n.pt")

            self.model = YOLO(person_model_path)

            try:
                # Move model to the selected device (GPU if available)
                self.model.to(self.device)
            except Exception as e:
                logger.warning(
                    f"Failed to move YOLO model to device '{self.device}': {e}. "
                    "Falling back to CPU."
                )
                self.device = "cpu"
                self.model.to(self.device)

            logger.info(f"Loaded YOLO model on device: {self.device}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model = None

        # Optional pose/violence detector
        self.pose_model = None
        self.violence_detector = None
        try:
            violence_enabled = bool(violence_cfg.get("enabled", False))

            violence_torchscript_path = models_cfg.get("violence_torchscript_path")
            if not violence_torchscript_path:
                for cand in [
                    "pose_model_torchscript.pt",
                    "violence_pose_torchscript.pt",
                    "violence_model_torchscript.pt",
                ]:
                    p = os.path.join(models_dir, cand)
                    if os.path.exists(p):
                        violence_torchscript_path = p
                        break

            pose_config_path = models_cfg.get("pose_config_path") or os.path.join(models_dir, "pose_config.json")

            pose_yolo_path = models_cfg.get("pose_yolo_path")
            if not pose_yolo_path:
                for cand in ["pose_yolo.pt", "yolov8n-pose.pt", "yolov8n-pose.onnx"]:
                    p = os.path.join(models_dir, cand)
                    if os.path.exists(p):
                        pose_yolo_path = p
                        break

            # If violence model exists but pose weights weren't dropped into /models,
            # fall back to downloading/loading by known YOLO name.
            if not pose_yolo_path:
                pose_yolo_path = violence_cfg.get("pose_yolo_default", "yolov8n-pose.pt")

            # If user didn't explicitly enable violence detection, auto-enable if the torchscript exists.
            if not violence_enabled:
                violence_enabled = bool(violence_torchscript_path and os.path.exists(violence_torchscript_path))

            if violence_enabled and violence_torchscript_path and pose_yolo_path:
                from ultralytics import YOLO

                self.pose_model = YOLO(pose_yolo_path)
                try:
                    self.pose_model.to(self.device)
                except Exception:
                    pass

                self.violence_detector = PoseViolenceDetector.from_config_files(
                    pose_yolo_model=self.pose_model,
                    violence_torchscript_path=violence_torchscript_path,
                    pose_config_path=pose_config_path if os.path.exists(pose_config_path) else None,
                    device=self.device,
                    overrides={
                        "violence_threshold": violence_cfg.get("violence_threshold", 0.7),
                        "inference_every_sec": violence_cfg.get("inference_every_sec", 1.0),
                        "event_cooldown_sec": violence_cfg.get("event_cooldown_sec", 10.0),
                        "pose_confidence_threshold": violence_cfg.get(
                            "pose_confidence_threshold", 0.3
                        ),
                    },
                )
                if self.violence_detector:
                    logger.info("Violence pose detector enabled")
            else:
                logger.info("Violence pose detector disabled (missing model paths)")
        except Exception as e:
            logger.warning(f"Violence pose detector initialization failed: {e}")
            self.violence_detector = None

        # Optional profanity detector (OCR + keywords)
        self.profanity_detector = None
        try:
            default_keywords_path = os.path.join(models_dir, "profanity_keywords_ru.txt")
            keywords_file = profanity_cfg.get("keywords_file") or default_keywords_path
            enabled = bool(profanity_cfg.get("enabled", False)) or os.path.exists(keywords_file)

            self.profanity_detector = ProfanityDetector.from_keywords_file(
                enabled=enabled,
                keywords_file=keywords_file if os.path.exists(keywords_file) else None,
                ocr_every_n_frames=profanity_cfg.get("ocr_every_n_frames", 15),
                event_cooldown_sec=profanity_cfg.get("event_cooldown_sec", 30.0),
                easyocr_languages=profanity_cfg.get("easyocr_languages", ["ru", "en"]),
                easyocr_use_gpu=bool(profanity_cfg.get("easyocr_use_gpu", False)),
                min_keywords_found=profanity_cfg.get("min_keywords_found", 1),
            )
            if self.profanity_detector and self.profanity_detector.enabled:
                logger.info("Profanity detector enabled")
        except Exception as e:
            logger.warning(f"Profanity detector initialization failed: {e}")
            self.profanity_detector = None
        
        self.running = False
        
    def connect(self):
        """Connect to RTSP stream"""
        logger.info(f"Connecting to camera {self.camera_name}: {self.rtsp_url}")
        
        self.cap = cv2.VideoCapture(self.rtsp_url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
        
        if not self.cap.isOpened():
            logger.error(f"Failed to open RTSP stream: {self.rtsp_url}")
            return False
        
        logger.info(f"Connected to camera {self.camera_name}")
        return True
    
    def disconnect(self):
        """Disconnect from stream"""
        if self.cap:
            self.cap.release()
            self.cap = None
    
    def detect_people(self, frame):
        """Detect people in frame using YOLO"""
        if self.model is None:
            return []
        
        try:
            # The model is already moved to the correct device in __init__
            results = self.model(
                frame,
                classes=self.person_class_ids,
                conf=self.person_conf,
                device=self.device,
                verbose=False,
            )
            detections = []
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])
                    
                    detections.append(Detection(
                        bbox=[float(x1), float(y1), float(x2), float(y2)],
                        confidence=conf,
                        frame_id=self.frame_count,
                        timestamp=time.time()
                    ))
            
            return detections
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return []
    
    async def process_frame(self):
        """Process single frame"""
        ret, frame = self.cap.read()
        if not ret:
            logger.warning(f"Failed to read frame from {self.camera_name}")
            return None
        
        self.frame_count += 1
        
        # Update FPS
        if time.time() - self.last_fps_update >= 1.0:
            self.fps = self.frame_count / (time.time() - self.last_fps_update)
            self.frame_count = 0
            self.last_fps_update = time.time()
        
        # Detect people
        detections = self.detect_people(frame)
        
        # Update tracker
        tracks = self.tracker.update(detections)
        
        # Detect risk events
        events = []
        height, width = frame.shape[:2]
        
        events.extend(self.risk_detector.detect_proximity_risk(tracks, width, height))
        events.extend(self.risk_detector.detect_crowd_risk(tracks, self.zones))
        events.extend(self.risk_detector.detect_kinetic_risk(tracks))

        # Optional: violence + profanity triggers
        if self.violence_detector:
            violence_event = self.violence_detector.update(frame)
            if violence_event:
                events.append(violence_event)

        if self.profanity_detector:
            profanity_event = self.profanity_detector.update(frame)
            if profanity_event:
                events.append(profanity_event)
        
        return {
            'camera_id': self.camera_id,
            'timestamp': datetime.now().isoformat(),
            'frame_id': self.frame_count,
            'fps': self.fps,
            'people_count': len(tracks),
            'tracks': [
                {
                    'track_id': t.track_id,
                    'bbox': t.bbox,
                    'confidence': t.confidence,
                    'velocity': t.velocity,
                    'acceleration': t.acceleration
                }
                for t in tracks if t.hits >= 3
            ],
            'events': events
        }
    
    async def run(self, event_queue: asyncio.Queue):
        """Main processing loop"""
        self.running = True
        
        while self.running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    if not self.connect():
                        await asyncio.sleep(5)  # Retry after 5 seconds
                        continue
                
                result = await self.process_frame()
                if result and result['events']:
                    await event_queue.put(result)
                
                await asyncio.sleep(0.01)  # Small delay to prevent CPU overload
                
            except Exception as e:
                logger.error(f"Error processing camera {self.camera_name}: {e}")
                self.disconnect()
                await asyncio.sleep(5)
    
    def stop(self):
        """Stop processing"""
        self.running = False
        self.disconnect()


async def send_events_to_risk_engine(event_queue: asyncio.Queue, risk_engine_url: str):
    """Send events to Risk Engine"""
    session = aiohttp.ClientSession()
    
    try:
        while True:
            result = await event_queue.get()
            
            try:
                async with session.post(
                    f"{risk_engine_url}/api/events",
                    json=result,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send events: {response.status}")
            except Exception as e:
                logger.error(f"Error sending events to risk engine: {e}")
            
    finally:
        await session.close()


async def register_camera_and_get_uuid(camera_config: dict, risk_engine_url: str) -> str:
    """Register camera in database and return UUID"""
    import uuid
    
    # Generate UUID from camera ID string (deterministic)
    camera_string_id = camera_config['id']
    camera_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, camera_string_id))
    
    # Try to register/update camera in database
    async with aiohttp.ClientSession() as session:
        try:
            camera_data = {
                "id": camera_uuid,
                "name": camera_config['name'],
                "rtsp_url": camera_config['rtsp_url'],
                "rtsp_substream_url": camera_config.get('rtsp_substream_url'),
                "location": camera_config.get('location', 'Unknown'),
                "fps": camera_config.get('fps', 15),
                "status": "online"
            }
            
            # Send PUT request to create or update camera
            async with session.put(
                f"{risk_engine_url}/api/cameras/{camera_uuid}",
                json=camera_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status in [200, 201]:
                    logger.info(f"Camera registered: {camera_config['name']} -> UUID: {camera_uuid}")
                else:
                    logger.warning(f"Failed to register camera: {response.status}")
        except Exception as e:
            logger.error(f"Error registering camera: {e}")
    
    return camera_uuid


async def send_camera_heartbeats(camera_ids: List[str], risk_engine_url: str):
    """Send periodic heartbeats for all cameras"""
    import aiohttp
    
    while True:
        try:
            await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            
            async with aiohttp.ClientSession() as session:
                for camera_id in camera_ids:
                    try:
                        async with session.post(
                            f"{risk_engine_url}/api/cameras/{camera_id}/heartbeat",
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            if response.status == 200:
                                logger.debug(f"Heartbeat sent for camera {camera_id}")
                    except Exception as e:
                        logger.error(f"Failed to send heartbeat for {camera_id}: {e}")
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")


async def main():
    """Main entry point"""
    logger.info("Starting DeepStream Analytics Service")
    
    # Load configuration
    default_config_path = os.path.join(os.path.dirname(__file__), "config", "analytics_config.yaml")
    config_path = os.getenv('CONFIG_PATH', default_config_path)
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}, using defaults")
        config = {
            'cameras': [],
            'risk_event_config': {}
        }
    
    # Default to localhost so analytics can talk to a locally running
    # Risk Engine on Windows; Docker overrides this via RISK_ENGINE_URL.
    risk_engine_url = os.getenv('RISK_ENGINE_URL', 'http://localhost:8001')
    
    # Initialize components
    risk_detector = RiskEventDetector(config.get('risk_event_config', {}))
    event_queue = asyncio.Queue()
    
    # Start event sender
    sender_task = asyncio.create_task(
        send_events_to_risk_engine(event_queue, risk_engine_url)
    )
    
    # Start camera processors
    processors = []
    camera_tasks = []
    camera_ids = []
    
    for camera_config in config.get('cameras', []):
        # Register camera and get UUID
        camera_uuid = await register_camera_and_get_uuid(camera_config, risk_engine_url)
        camera_ids.append(camera_uuid)
        
        # Update config with UUID
        camera_config['id'] = camera_uuid
        
        processor = CameraProcessor(camera_config, risk_detector, config)
        processors.append(processor)
        
        task = asyncio.create_task(processor.run(event_queue))
        camera_tasks.append(task)
    
    # Start heartbeat sender
    heartbeat_task = asyncio.create_task(
        send_camera_heartbeats(camera_ids, risk_engine_url)
    )
    
    logger.info(f"Started processing {len(processors)} cameras with heartbeat monitoring")
    
    # Wait for all tasks
    try:
        await asyncio.gather(*camera_tasks, sender_task, heartbeat_task)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for processor in processors:
            processor.stop()


if __name__ == '__main__':
    asyncio.run(main())
