import React, { useState, useEffect, useRef } from 'react';
import '../styles/LiveCameraView.css';

const LiveCameraView = ({ camera, onClose }) => {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const videoRef = useRef(null);
  const containerRef = useRef(null);

  const streamUrl = `http://localhost:8003/stream/${camera.id}`;

  useEffect(() => {
    const img = videoRef.current;
    
    const handleLoad = () => {
      setIsLoading(false);
      setError(null);
    };
    
    const handleError = () => {
      setIsLoading(false);
      setError('Failed to load stream');
    };

    if (img) {
      img.addEventListener('load', handleLoad);
      img.addEventListener('error', handleError);
    }

    return () => {
      if (img) {
        img.removeEventListener('load', handleLoad);
        img.removeEventListener('error', handleError);
      }
    };
  }, [camera.id]);

  const toggleFullscreen = () => {
    if (!isFullscreen) {
      if (containerRef.current.requestFullscreen) {
        containerRef.current.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    setIsFullscreen(!isFullscreen);
  };

  return (
    <div className={`live-camera-container ${isFullscreen ? 'fullscreen' : ''}`} ref={containerRef}>
      <div className="live-camera-header">
        <div className="camera-info">
          <span className="live-indicator">● LIVE</span>
          <h3>{camera.name}</h3>
          <span className="camera-location">{camera.location}</span>
        </div>
        
        <div className="camera-controls">
          <button onClick={toggleFullscreen} className="btn-icon">
            {isFullscreen ? '⊗' : '⛶'}
          </button>
          <button onClick={onClose} className="btn-icon">✕</button>
        </div>
      </div>

      <div className="live-camera-body">
        {isLoading && (
          <div className="stream-loading">
            <div className="spinner"></div>
            <p>Connecting to stream...</p>
          </div>
        )}
        
        {error && (
          <div className="stream-error">
            <p>⚠️ {error}</p>
            <button onClick={() => window.location.reload()} className="btn-retry">
              Retry
            </button>
          </div>
        )}

        <img
          ref={videoRef}
          src={streamUrl}
          alt={`Live stream from ${camera.name}`}
          className="live-stream"
          style={{ display: isLoading || error ? 'none' : 'block' }}
        />
      </div>

      <div className="live-camera-footer">
        <div className="stream-stats">
          <span>🟢 Connected</span>
          <span>FPS: ~{camera.fps || 15}</span>
          <span>{new Date().toLocaleTimeString()}</span>
        </div>
      </div>
    </div>
  );
};

export default LiveCameraView;
