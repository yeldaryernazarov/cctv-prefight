#!/usr/bin/env python3
"""
Stream Server - Provides live MJPEG streams with YOLO detections
"""

import cv2
import asyncio
import aiohttp
from aiohttp import web
import numpy as np
from collections import defaultdict
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamServer:
    """Serves MJPEG streams with detection overlays"""
    
    def __init__(self):
        self.streams = {}  # camera_id -> frame buffer
        self.detections = defaultdict(list)  # camera_id -> list of detections
        
    def update_frame(self, camera_id: str, frame: np.ndarray, detections: list):
        """Update frame with detections"""
        
        # Draw detections on frame
        annotated_frame = frame.copy()
        
        for det in detections:
            bbox = det['bbox']
            track_id = det.get('track_id', '?')
            confidence = det.get('confidence', 0.0)
            
            # Draw bounding box
            x1, y1, x2, y2 = map(int, bbox)
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label
            label = f"ID:{track_id} {confidence:.2f}"
            cv2.putText(
                annotated_frame, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
            )
        
        # Add timestamp
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(
            annotated_frame, timestamp, (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
        )
        
        # Add LIVE indicator
        cv2.putText(
            annotated_frame, "LIVE", (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
        )
        
        # Encode as JPEG
        ret, jpeg = cv2.imencode('.jpg', annotated_frame)
        if ret:
            self.streams[camera_id] = jpeg.tobytes()
    
    async def stream_handler(self, request):
        """Handle MJPEG stream requests"""
        camera_id = request.match_info['camera_id']
        
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'multipart/x-mixed-replace; boundary=frame',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
        )
        await response.prepare(request)
        
        try:
            while True:
                if camera_id in self.streams:
                    frame = self.streams[camera_id]
                    
                    await response.write(
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                    )
                
                await asyncio.sleep(0.033)  # ~30 fps
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Stream error for camera {camera_id}: {e}")
        
        return response
    
    async def list_cameras(self, request):
        """List available camera streams"""
        return web.json_response({
            'cameras': list(self.streams.keys())
        })


async def create_app():
    """Create aiohttp application"""
    server = StreamServer()
    
    app = web.Application()
    app['stream_server'] = server
    
    # Routes
    app.router.add_get('/stream/{camera_id}', server.stream_handler)
    app.router.add_get('/api/cameras', server.list_cameras)
    
    # CORS
    from aiohttp_cors import setup as cors_setup, ResourceOptions
    cors = cors_setup(app, defaults={
        "*": ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*"
        )
    })
    
    for route in list(app.router.routes()):
        cors.add(route)
    
    return app


if __name__ == '__main__':
    web.run_app(create_app(), host='0.0.0.0', port=8003)
