import React, { useState, useEffect } from 'react';
import { dashboard, alerts } from '../services/api';
import { useNavigate } from 'react-router-dom';

function DashboardPage({ user }) {
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    active_alerts: 0,
    today_alerts: 0,
    online_cameras: 0,
    total_cameras: 0
  });
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      const statsResponse = await dashboard.getStats();
      setStats(statsResponse.data);

      const alertsResponse = await alerts.getAll({
        status: 'new',
        limit: 5
      });
      setRecentAlerts(alertsResponse.data.slice(0, 5));

      setLoading(false);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setLoading(false);
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return '#dc3545';
      case 'high': return '#fd7e14';
      case 'medium': return '#ffc107';
      case 'low': return '#28a745';
      default: return '#6c757d';
    }
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);

    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;

    return date.toLocaleString();
  };

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '30px' }}>Dashboard</h1>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: '20px',
        marginBottom: '30px'
      }}>
        <StatCard
          title="Active Cameras"
          value={`${stats.online_cameras}/${stats.total_cameras}`}
          subtitle={stats.online_cameras === stats.total_cameras ? 'All online' : 'Some offline'}
          icon="📹"
          color={stats.online_cameras === stats.total_cameras ? '#4CAF50' : '#FF9800'}
          loading={loading}
          onClick={() => navigate('/cameras')}
        />
        <StatCard
          title="Active Alerts"
          value={stats.active_alerts}
          subtitle="Needs attention"
          icon="⚠️"
          color={stats.active_alerts > 0 ? '#dc3545' : '#4CAF50'}
          loading={loading}
          pulse={stats.active_alerts > 0}
          onClick={() => navigate('/alerts')}
        />
        <StatCard
          title="Today's Alerts"
          value={stats.today_alerts}
          subtitle="Last 24 hours"
          icon="📊"
          color="#2196F3"
          loading={loading}
        />
        <StatCard
          title="System Status"
          value={stats.online_cameras > 0 ? 'Operational' : 'Offline'}
          subtitle="AI Detection Active"
          icon={stats.online_cameras > 0 ? '✅' : '⚠️'}
          color={stats.online_cameras > 0 ? '#8BC34A' : '#FF9800'}
          loading={loading}
        />
      </div>

      <div style={{
        background: 'white',
        padding: '24px',
        borderRadius: '8px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        marginBottom: '20px'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px'
        }}>
          <h2 style={{ margin: 0, fontSize: '20px' }}>Recent Alerts</h2>
          <button
            onClick={() => navigate('/alerts')}
            style={{
              padding: '8px 16px',
              background: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            View All
          </button>
        </div>

        {loading ? (
          <p style={{ textAlign: 'center', color: '#666' }}>Loading alerts...</p>
        ) : recentAlerts.length === 0 ? (
          <div style={{
            padding: '40px',
            textAlign: 'center',
            background: '#f8f9fa',
            borderRadius: '6px'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '10px' }}>✅</div>
            <p style={{ fontSize: '18px', color: '#666', margin: 0 }}>
              No active alerts
            </p>
            <p style={{ fontSize: '14px', color: '#999', marginTop: '8px' }}>
              System is monitoring normally
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {recentAlerts.map((alert) => (
              <div
                key={alert.id}
                onClick={() => navigate(`/alerts/${alert.id}`)}
                style={{
                  padding: '16px',
                  background: '#f8f9fa',
                  borderRadius: '6px',
                  borderLeft: `4px solid ${getSeverityColor(alert.severity)}`,
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#e9ecef'}
                onMouseLeave={(e) => e.currentTarget.style.background = '#f8f9fa'}
              >
                <div>
                  <div style={{
                    fontWeight: 'bold',
                    marginBottom: '4px',
                    color: getSeverityColor(alert.severity)
                  }}>
                    {alert.severity.toUpperCase()} - Score: {alert.risk_score.toFixed(1)}
                  </div>
                  <div style={{ fontSize: '14px', color: '#666' }}>
                    {alert.camera?.name || alert.camera_id} • {formatTimestamp(alert.timestamp)}
                  </div>
                  {alert.event_summary && alert.event_summary.length > 0 && (
                    <div style={{
                      fontSize: '12px',
                      color: '#999',
                      marginTop: '4px'
                    }}>
                      {alert.event_summary.length} event(s) detected
                    </div>
                  )}
                </div>
                <div style={{ fontSize: '24px' }}>→</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{
        background: 'white',
        padding: '24px',
        borderRadius: '8px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        <h2 style={{ marginBottom: '20px' }}>Welcome, {user?.name || 'User'}!</h2>
        <p>The School Risk Detection system is monitoring your cameras for potential safety risks.</p>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          marginTop: '24px'
        }}>
          <div style={{
            padding: '16px',
            background: '#e8f5e9',
            borderRadius: '6px',
            borderLeft: '4px solid #4CAF50'
          }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>✅</div>
            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>Real-time Monitoring</div>
            <div style={{ fontSize: '14px', color: '#666' }}>
              Cameras are being monitored 24/7
            </div>
          </div>

          <div style={{
            padding: '16px',
            background: '#e3f2fd',
            borderRadius: '6px',
            borderLeft: '4px solid #2196F3'
          }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>🔍</div>
            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>AI Detection</div>
            <div style={{ fontSize: '14px', color: '#666' }}>
              Advanced AI analyzes behavior patterns
            </div>
          </div>

          <div style={{
            padding: '16px',
            background: '#fff3e0',
            borderRadius: '6px',
            borderLeft: '4px solid #FF9800'
          }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>📱</div>
            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>Instant Alerts</div>
            <div style={{ fontSize: '14px', color: '#666' }}>
              Get notified immediately of risks
            </div>
          </div>

          <div style={{
            padding: '16px',
            background: '#fce4ec',
            borderRadius: '6px',
            borderLeft: '4px solid #E91E63'
          }}>
            <div style={{ fontSize: '24px', marginBottom: '8px' }}>🎥</div>
            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>Video Evidence</div>
            <div style={{ fontSize: '14px', color: '#666' }}>
              Automatic clip saving for review
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, subtitle, icon, color, loading, pulse, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: 'white',
        padding: '20px',
        borderRadius: '8px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        borderLeft: `4px solid ${color}`,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'transform 0.2s, box-shadow 0.2s'
      }}
      onMouseEnter={(e) => {
        if (onClick) {
          e.currentTarget.style.transform = 'translateY(-2px)';
          e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
        }
      }}
      onMouseLeave={(e) => {
        if (onClick) {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
        }
      }}
    >
      <div style={{ fontSize: '32px', marginBottom: '10px' }}>{icon}</div>
      <h3 style={{ fontSize: '14px', color: '#666', marginBottom: '5px' }}>{title}</h3>
      {loading ? (
        <p style={{ fontSize: '20px', color: '#999' }}>Loading...</p>
      ) : (
        <>
          <p style={{ fontSize: '28px', fontWeight: 'bold', margin: 0, color: color }}>
            {value}
          </p>
          {subtitle && (
            <p style={{ fontSize: '12px', color: '#999', marginTop: '4px', marginBottom: 0 }}>
              {subtitle}
            </p>
          )}
        </>
      )}
    </div>
  );
}

export default DashboardPage;