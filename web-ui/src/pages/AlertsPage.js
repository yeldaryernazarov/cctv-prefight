import React, { useState, useEffect } from 'react';
import { alerts } from '../services/api';
import { useNavigate } from 'react-router-dom';

function AlertsPage() {
  const [alertsList, setAlertsList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const navigate = useNavigate();

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 5000);
    return () => clearInterval(interval);
  }, [filter]);

  const fetchAlerts = async () => {
    try {
      const params = {};

      if (filter === 'new') {
        params.status = 'new';
      } else if (filter === 'in_review') {
        params.status = 'in_review';
      } else if (filter === 'critical') {
        params.severity = 'critical';
      }

      const response = await alerts.getAll(params);
      setAlertsList(response.data);
      setError(null);
    } catch (err) {
      console.error('Error fetching alerts:', err);
      setError('Failed to load alerts');
    } finally {
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

  const getStatusBadge = (status) => {
    const statusColors = {
      'new': '#dc3545',
      'in_review': '#ffc107',
      'confirmed': '#fd7e14',
      'false_positive': '#6c757d',
      'escalated': '#e83e8c',
      'closed': '#28a745'
    };

    const statusLabels = {
      'new': 'New',
      'in_review': 'In Review',
      'confirmed': 'Confirmed',
      'false_positive': 'False Positive',
      'escalated': 'Escalated',
      'closed': 'Closed'
    };

    return (
      <span style={{
        padding: '4px 8px',
        borderRadius: '4px',
        fontSize: '12px',
        fontWeight: 'bold',
        color: 'white',
        backgroundColor: statusColors[status] || '#6c757d'
      }}>
        {statusLabels[status] || status}
      </span>
    );
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);

    if (diff < 60) return `${diff} seconds ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;

    return date.toLocaleString();
  };

  if (loading) {
    return (
      <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
        <h1>Alerts</h1>
        <div style={{
          background: 'white',
          padding: '40px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          textAlign: 'center'
        }}>
          <p>Loading alerts...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
        <h1>Alerts</h1>
        <div style={{
          background: 'white',
          padding: '40px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          textAlign: 'center'
        }}>
          <p style={{ color: '#dc3545' }}>{error}</p>
          <button
            onClick={fetchAlerts}
            style={{
              marginTop: '20px',
              padding: '10px 20px',
              background: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px'
      }}>
        <h1 style={{ margin: 0 }}>Alerts ({alertsList.length})</h1>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => setFilter('all')}
            style={{
              padding: '8px 16px',
              background: filter === 'all' ? '#007bff' : '#f8f9fa',
              color: filter === 'all' ? 'white' : '#333',
              border: '1px solid #dee2e6',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            All
          </button>
          <button
            onClick={() => setFilter('new')}
            style={{
              padding: '8px 16px',
              background: filter === 'new' ? '#007bff' : '#f8f9fa',
              color: filter === 'new' ? 'white' : '#333',
              border: '1px solid #dee2e6',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            New
          </button>
          <button
            onClick={() => setFilter('critical')}
            style={{
              padding: '8px 16px',
              background: filter === 'critical' ? '#007bff' : '#f8f9fa',
              color: filter === 'critical' ? 'white' : '#333',
              border: '1px solid #dee2e6',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Critical
          </button>
        </div>
      </div>

      {alertsList.length === 0 ? (
        <div style={{
          background: 'white',
          padding: '40px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          textAlign: 'center'
        }}>
          <p style={{ fontSize: '18px', color: '#666' }}>No alerts found</p>
          <p style={{ marginTop: '10px', color: '#999' }}>
            {filter === 'all'
              ? 'Alerts will appear here when risk events are detected'
              : `No ${filter} alerts at this time`
            }
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          {alertsList.map((alert) => (
            <div
              key={alert.id}
              onClick={() => navigate(`/alerts/${alert.id}`)}
              style={{
                background: 'white',
                padding: '20px',
                borderRadius: '8px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                cursor: 'pointer',
                borderLeft: `4px solid ${getSeverityColor(alert.severity)}`,
                transition: 'transform 0.2s, box-shadow 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
              }}
            >
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: '12px'
              }}>
                <div>
                  <h3 style={{
                    margin: '0 0 8px 0',
                    fontSize: '18px',
                    fontWeight: 'bold'
                  }}>
                    Alert #{alert.id.slice(0, 8)}
                  </h3>
                  <div style={{
                    fontSize: '14px',
                    color: '#666',
                    marginBottom: '4px'
                  }}>
                    Camera: {alert.camera?.name || alert.camera_id}
                  </div>
                  <div style={{ fontSize: '14px', color: '#999' }}>
                    {formatTimestamp(alert.timestamp)}
                  </div>
                </div>

                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-end',
                  gap: '8px'
                }}>
                  {getStatusBadge(alert.status)}
                  <div style={{
                    fontSize: '14px',
                    fontWeight: 'bold',
                    color: getSeverityColor(alert.severity)
                  }}>
                    {alert.severity.toUpperCase()}
                  </div>
                </div>
              </div>

              <div style={{
                display: 'flex',
                gap: '20px',
                padding: '12px',
                background: '#f8f9fa',
                borderRadius: '4px'
              }}>
                <div>
                  <div style={{ fontSize: '12px', color: '#666' }}>Risk Score</div>
                  <div style={{
                    fontSize: '20px',
                    fontWeight: 'bold',
                    color: getSeverityColor(alert.severity)
                  }}>
                    {alert.risk_score.toFixed(1)}
                  </div>
                </div>

                {alert.event_summary && alert.event_summary.length > 0 && (
                  <div>
                    <div style={{ fontSize: '12px', color: '#666' }}>Events</div>
                    <div style={{ fontSize: '14px', fontWeight: 'bold' }}>
                      {alert.event_summary.length} detected
                    </div>
                  </div>
                )}
              </div>

              {alert.event_summary && alert.event_summary.length > 0 && (
                <div style={{ marginTop: '12px' }}>
                  <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
                    Event Types:
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {[...new Set(alert.event_summary.map(e => e.type))].map((type, idx) => (
                      <span
                        key={idx}
                        style={{
                          padding: '4px 8px',
                          background: '#e9ecef',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: '500'
                        }}
                      >
                        {type}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AlertsPage;