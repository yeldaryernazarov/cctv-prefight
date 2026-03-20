import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { alerts } from '../services/api';

function AlertDetailPage() {
  const { alertId } = useParams();
  const navigate = useNavigate();
  const [alert, setAlert] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [decision, setDecision] = useState('');
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchAlertDetails();
  }, [alertId]);

  const fetchAlertDetails = async () => {
    try {
      const response = await alerts.getById(alertId);
      setAlert(response.data);
      setError(null);
    } catch (err) {
      console.error('Error fetching alert details:', err);
      setError('Failed to load alert details');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitDecision = async (e) => {
    e.preventDefault();

    if (!decision) {
      window.alert('Please select a decision');
      return;
    }

    setSubmitting(true);
    try {
      await alerts.createDecision(alertId, {
        decision,
        comment
      });

      await fetchAlertDetails();

      setDecision('');
      setComment('');

      window.alert('Decision submitted successfully');
    } catch (err) {
      console.error('Error submitting decision:', err);
      window.alert('Failed to submit decision');
    } finally {
      setSubmitting(false);
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
        padding: '6px 12px',
        borderRadius: '4px',
        fontSize: '14px',
        fontWeight: 'bold',
        color: 'white',
        backgroundColor: statusColors[status] || '#6c757d'
      }}>
        {statusLabels[status] || status}
      </span>
    );
  };

  if (loading) {
    return (
      <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
        <button
          onClick={() => navigate('/alerts')}
          style={{
            marginBottom: '20px',
            padding: '8px 16px',
            background: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          ← Back to Alerts
        </button>
        <h1>Alert Details</h1>
        <div style={{
          background: 'white',
          padding: '40px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          textAlign: 'center'
        }}>
          <p>Loading alert details...</p>
        </div>
      </div>
    );
  }

  if (error || !alert) {
    return (
      <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
        <button
          onClick={() => navigate('/alerts')}
          style={{
            marginBottom: '20px',
            padding: '8px 16px',
            background: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          ← Back to Alerts
        </button>
        <h1>Alert Details</h1>
        <div style={{
          background: 'white',
          padding: '40px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          textAlign: 'center'
        }}>
          <p style={{ color: '#dc3545' }}>{error || 'Alert not found'}</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <button
        onClick={() => navigate('/alerts')}
        style={{
          marginBottom: '20px',
          padding: '8px 16px',
          background: '#6c757d',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer'
        }}
      >
        ← Back to Alerts
      </button>

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '20px'
      }}>
        <h1 style={{ margin: 0 }}>Alert #{alert.id.slice(0, 8)}</h1>
        {getStatusBadge(alert.status)}
      </div>

      <div style={{
        background: 'white',
        padding: '24px',
        borderRadius: '8px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        marginBottom: '20px',
        borderLeft: `6px solid ${getSeverityColor(alert.severity)}`
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '24px'
        }}>
          <div>
            <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
              Severity
            </div>
            <div style={{
              fontSize: '20px',
              fontWeight: 'bold',
              color: getSeverityColor(alert.severity)
            }}>
              {alert.severity.toUpperCase()}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
              Risk Score
            </div>
            <div style={{
              fontSize: '20px',
              fontWeight: 'bold',
              color: getSeverityColor(alert.severity)
            }}>
              {alert.risk_score.toFixed(2)}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
              Camera
            </div>
            <div style={{ fontSize: '16px', fontWeight: '500' }}>
              {alert.camera?.name || alert.camera_id}
            </div>
            {alert.camera?.location && (
              <div style={{ fontSize: '14px', color: '#999', marginTop: '2px' }}>
                {alert.camera.location}
              </div>
            )}
          </div>

          <div>
            <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
              Timestamp
            </div>
            <div style={{ fontSize: '14px' }}>
              {new Date(alert.timestamp).toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {alert.event_summary && alert.event_summary.length > 0 && (
        <div style={{
          background: 'white',
          padding: '24px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          marginBottom: '20px'
        }}>
          <h2 style={{ marginTop: 0, marginBottom: '16px', fontSize: '18px' }}>
            Detected Events ({alert.event_summary.length})
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {alert.event_summary.map((event, idx) => (
              <div
                key={idx}
                style={{
                  padding: '16px',
                  background: '#f8f9fa',
                  borderRadius: '6px',
                  border: '1px solid #dee2e6'
                }}
              >
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '8px'
                }}>
                  <span style={{
                    fontWeight: 'bold',
                    fontSize: '14px'
                  }}>
                    {event.type}
                  </span>
                  <span style={{
                    fontSize: '12px',
                    color: '#666'
                  }}>
                    Confidence: {(event.confidence * 100).toFixed(1)}%
                  </span>
                </div>

                {event.track_ids && event.track_ids.length > 0 && (
                  <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>
                    Involved tracks: {event.track_ids.join(', ')}
                  </div>
                )}

                {event.meta_data && Object.keys(event.meta_data).length > 0 && (
                  <div style={{
                    marginTop: '8px',
                    fontSize: '12px',
                    fontFamily: 'monospace',
                    background: 'white',
                    padding: '8px',
                    borderRadius: '4px',
                    overflow: 'auto'
                  }}>
                    <pre style={{ margin: 0 }}>
                      {JSON.stringify(event.meta_data, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {alert.clip_url && (
        <div style={{
          background: 'white',
          padding: '24px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          marginBottom: '20px'
        }}>
          <h2 style={{ marginTop: 0, marginBottom: '16px', fontSize: '18px' }}>
            Video Clip
          </h2>
          <video
            controls
            style={{
              width: '100%',
              maxHeight: '500px',
              borderRadius: '6px',
              background: '#000'
            }}
          >
            <source src={alert.clip_url} type="video/mp4" />
            Your browser does not support the video tag.
          </video>
        </div>
      )}

      {alert.decisions && alert.decisions.length > 0 && (
        <div style={{
          background: 'white',
          padding: '24px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          marginBottom: '20px'
        }}>
          <h2 style={{ marginTop: 0, marginBottom: '16px', fontSize: '18px' }}>
            Decision History
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {alert.decisions.map((dec, idx) => (
              <div
                key={idx}
                style={{
                  padding: '16px',
                  background: '#f8f9fa',
                  borderRadius: '6px',
                  border: '1px solid #dee2e6'
                }}
              >
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: '8px'
                }}>
                  <span style={{ fontWeight: 'bold' }}>
                    {dec.decision.replace('_', ' ').toUpperCase()}
                  </span>
                  <span style={{ fontSize: '12px', color: '#666' }}>
                    {new Date(dec.created_at).toLocaleString()}
                  </span>
                </div>

                {dec.comment && (
                  <div style={{ fontSize: '14px', color: '#333', marginTop: '8px' }}>
                    {dec.comment}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {alert.status === 'new' || alert.status === 'in_review' ? (
        <div style={{
          background: 'white',
          padding: '24px',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <h2 style={{ marginTop: 0, marginBottom: '16px', fontSize: '18px' }}>
            Make Decision
          </h2>

          <form onSubmit={handleSubmitDecision}>
            <div style={{ marginBottom: '16px' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                fontWeight: '500'
              }}>
                Decision *
              </label>
              <select
                value={decision}
                onChange={(e) => setDecision(e.target.value)}
                required
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '4px',
                  border: '1px solid #dee2e6',
                  fontSize: '14px'
                }}
              >
                <option value="">Select a decision...</option>
                <option value="confirmed">Confirmed - Real threat</option>
                <option value="false_positive">False Positive - No threat</option>
                <option value="escalated">Escalate - Needs immediate attention</option>
              </select>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                fontWeight: '500'
              }}>
                Comments
              </label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Add any additional notes or observations..."
                rows={4}
                style={{
                  width: '100%',
                  padding: '10px',
                  borderRadius: '4px',
                  border: '1px solid #dee2e6',
                  fontSize: '14px',
                  fontFamily: 'inherit',
                  resize: 'vertical'
                }}
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: '12px 24px',
                background: submitting ? '#6c757d' : '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: submitting ? 'not-allowed' : 'pointer'
              }}
            >
              {submitting ? 'Submitting...' : 'Submit Decision'}
            </button>
          </form>
        </div>
      ) : (
        <div style={{
          background: '#f8f9fa',
          padding: '20px',
          borderRadius: '8px',
          textAlign: 'center',
          color: '#666'
        }}>
          This alert has been closed. Status: {alert.status}
        </div>
      )}
    </div>
  );
}

export default AlertDetailPage;