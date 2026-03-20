import React, { useState, useEffect } from 'react';
import { cameras } from '../services/api';
import LiveCameraView from '../components/LiveCameraView';

function CamerasPage() {
  const [cameraList, setCameraList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedCamera, setSelectedCamera] = useState(null);

  useEffect(() => {
    loadCameras();
    const interval = setInterval(loadCameras, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const loadCameras = async () => {
    try {
      const response = await cameras.getAll();
      setCameraList(response.data);
      setError(null);
    } catch (err) {
      console.error('Failed to load cameras:', err);
      setError('Failed to load cameras');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ fontSize: '18px', color: '#666' }}>Loading cameras...</div>
      </div>
    );
  }

  return (
    <div style={{ 
      padding: '30px',
      maxWidth: '1400px',
      margin: '0 auto',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      minHeight: '100vh'
    }}>
      <div style={{
        background: 'white',
        borderRadius: '15px',
        padding: '40px',
        boxShadow: '0 10px 40px rgba(0,0,0,0.2)'
      }}>
        {selectedCamera && (
          <div style={{ marginBottom: '30px' }}>
            <LiveCameraView
              camera={selectedCamera}
              onClose={() => setSelectedCamera(null)}
            />
          </div>
        )}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '30px'
        }}>
          <h1 style={{ margin: 0 }}>
            📹 Camera Management
          </h1>
          <div style={{
            padding: '10px 20px',
            background: cameraList.filter(c => c.status === 'online').length > 0 ? '#4CAF50' : '#f44336',
            color: 'white',
            borderRadius: '25px',
            fontWeight: 'bold'
          }}>
            {cameraList.filter(c => c.status === 'online').length}/{cameraList.length} Online
          </div>
        </div>

        {error && (
          <div style={{
            padding: '15px',
            background: '#ffebee',
            color: '#c62828',
            borderRadius: '8px',
            marginBottom: '20px'
          }}>
            {error}
          </div>
        )}

        {/* Camera Grid */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
          gap: '25px'
        }}>
          {cameraList.map(camera => (
            <div 
              key={camera.id}
              style={{
                background: 'white',
                padding: '25px',
                borderRadius: '12px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                border: `3px solid ${camera.status === 'online' ? '#4CAF50' : '#f44336'}`,
                transition: 'all 0.3s'
              }}
            >
              {/* Status Badge */}
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between',
                alignItems: 'start',
                marginBottom: '15px'
              }}>
                <div style={{ flex: 1 }}>
                  <h2 style={{ 
                    margin: '0 0 10px 0',
                    fontSize: '22px',
                    color: '#333'
                  }}>
                    {camera.name}
                  </h2>
                  <div style={{ 
                    fontSize: '14px',
                    color: '#666',
                    marginBottom: '8px'
                  }}>
                    📍 {camera.location || 'No location'}
                  </div>
                </div>
                
                <div style={{
                  padding: '8px 16px',
                  borderRadius: '20px',
                  background: camera.status === 'online' ? '#4CAF50' : '#f44336',
                  color: 'white',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  textTransform: 'uppercase',
                  whiteSpace: 'nowrap'
                }}>
                  {camera.status === 'online' ? '● ONLINE' : '○ OFFLINE'}
                </div>
              </div>

              {/* Camera Info */}
              <div style={{
                background: '#f5f5f5',
                padding: '15px',
                borderRadius: '8px',
                marginBottom: '15px'
              }}>
                <div style={{ 
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '12px',
                  fontSize: '14px'
                }}>
                  <div>
                    <div style={{ color: '#999', marginBottom: '4px' }}>FPS</div>
                    <div style={{ fontWeight: 'bold', color: '#333' }}>
                      {camera.fps || 15}
                    </div>
                  </div>
                  
                  <div>
                    <div style={{ color: '#999', marginBottom: '4px' }}>Resolution</div>
                    <div style={{ fontWeight: 'bold', color: '#333' }}>
                      {camera.resolution || '1920x1080'}
                    </div>
                  </div>
                  
                  <div style={{ gridColumn: '1 / -1' }}>
                    <div style={{ color: '#999', marginBottom: '4px' }}>Last Seen</div>
                    <div style={{ fontWeight: 'bold', color: '#333' }}>
                      {camera.last_seen 
                        ? new Date(camera.last_seen).toLocaleString()
                        : 'Never'
                      }
                    </div>
                  </div>
                </div>
              </div>

              {/* Live View Notice */}
              <div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #eee' }}>
                {camera.status === 'online' ? (
                  <button
                    onClick={() => setSelectedCamera(camera)}
                    style={{
                      width: '100%',
                      padding: '10px 16px',
                      borderRadius: '8px',
                      border: 'none',
                      cursor: 'pointer',
                      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      color: 'white',
                      fontWeight: 'bold',
                      fontSize: '14px',
                      boxShadow: '0 4px 10px rgba(0,0,0,0.2)',
                      transition: 'transform 0.1s ease, box-shadow 0.1s ease',
                    }}
                    onMouseDown={e => {
                      e.currentTarget.style.transform = 'scale(0.98)';
                      e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.2)';
                    }}
                    onMouseUp={e => {
                      e.currentTarget.style.transform = 'scale(1)';
                      e.currentTarget.style.boxShadow = '0 4px 10px rgba(0,0,0,0.2)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.transform = 'scale(1)';
                      e.currentTarget.style.boxShadow = '0 4px 10px rgba(0,0,0,0.2)';
                    }}
                  >
                    📹 View Live Stream with AI
                  </button>
                ) : (
                  <div style={{
                    padding: '12px',
                    background: '#f5f5f5',
                    borderRadius: '8px',
                    color: '#999',
                    fontSize: '13px',
                    textAlign: 'center'
                  }}>
                    Live view available when camera is online
                  </div>
                )}
              </div>

              {/* RTSP Info (for admins) */}
              {camera.rtsp_url && (
                <details style={{ marginTop: '15px' }}>
                  <summary style={{ 
                    cursor: 'pointer',
                    fontSize: '12px',
                    color: '#666',
                    padding: '8px',
                    background: '#f9f9f9',
                    borderRadius: '4px'
                  }}>
                    🔧 Technical Details
                  </summary>
                  <div style={{
                    marginTop: '8px',
                    padding: '10px',
                    background: '#f5f5f5',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    wordBreak: 'break-all',
                    color: '#666'
                  }}>
                    <div><strong>RTSP:</strong> {camera.rtsp_url.substring(0, 50)}...</div>
                    <div style={{ marginTop: '4px' }}>
                      <strong>ID:</strong> {camera.id}
                    </div>
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>

        {/* Empty State */}
        {cameraList.length === 0 && !loading && (
          <div style={{
            background: 'white',
            padding: '60px 40px',
            borderRadius: '12px',
            textAlign: 'center',
            border: '2px dashed #ddd'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '20px' }}>📹</div>
            <h2 style={{ color: '#333', marginBottom: '15px' }}>No Cameras Configured</h2>
            <p style={{ color: '#666', marginBottom: '30px', lineHeight: '1.6' }}>
              No cameras are currently registered in the system.
            </p>
            
            <div style={{
              background: '#e3f2fd',
              padding: '25px',
              borderRadius: '8px',
              textAlign: 'left',
              maxWidth: '600px',
              margin: '0 auto'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '15px', color: '#1976d2' }}>
                📱 To add cameras:
              </div>
              <ol style={{ 
                paddingLeft: '20px',
                color: '#666',
                lineHeight: '1.8'
              }}>
                <li>Edit <code style={{ 
                  background: '#fff',
                  padding: '2px 8px',
                  borderRadius: '3px',
                  fontFamily: 'monospace'
                }}>configs/cameras.yaml</code></li>
                <li>Add your RTSP camera streams</li>
                <li>Restart: <code style={{
                  background: '#fff',
                  padding: '2px 8px',
                  borderRadius: '3px',
                  fontFamily: 'monospace'
                }}>docker-compose restart deepstream-analytics</code></li>
                <li>Cameras will appear here automatically</li>
              </ol>
            </div>
          </div>
        )}

        {/* Info Box */}
        <div style={{
          marginTop: '30px',
          padding: '20px',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderRadius: '12px',
          color: 'white'
        }}>
          <h3 style={{ marginTop: 0 }}>ℹ️ About Camera System</h3>
          <p style={{ margin: '10px 0', lineHeight: '1.6' }}>
            Cameras are automatically registered when the analytics service starts. 
            Each camera processes video in real-time using AI to detect risk events.
          </p>
          <p style={{ margin: '10px 0', lineHeight: '1.6', fontSize: '14px', opacity: 0.9 }}>
            Status updates every 30 seconds. Live video preview will be available in future updates.
          </p>
        </div>
      </div>
    </div>
  );
}

export default CamerasPage;
