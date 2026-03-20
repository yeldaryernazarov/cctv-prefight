// This file contains simplified React components
// In production, these would be separate files

// LoginPage.js
import React, { useState } from 'react';
import { auth } from '../services/api';

export function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await auth.login(username, password);
      onLogin(response.data.access_token, {
        id: response.data.user_id,
        username: response.data.username,
        role: response.data.role
      });
    } catch (err) {
      setError('Invalid credentials');
    }
  };

  return (
    <div className="login-page">
      <form onSubmit={handleSubmit}>
        <h2>School Risk Detection</h2>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="error">{error}</p>}
        <button type="submit">Login</button>
      </form>
    </div>
  );
}

// DashboardPage.js
import React, { useState, useEffect } from 'react';
import { dashboard, cameras } from '../services/api';

export function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [cameraList, setCameraList] = useState([]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [statsRes, camerasRes] = await Promise.all([
        dashboard.getStats(),
        cameras.getAll()
      ]);
      setStats(statsRes.data);
      setCameraList(camerasRes.data);
    } catch (err) {
      console.error('Error loading dashboard:', err);
    }
  };

  return (
    <div className="dashboard-page">
      <h1>Dashboard</h1>
      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <h3>Active Alerts</h3>
            <p className="stat-value">{stats.active_alerts}</p>
          </div>
          <div className="stat-card">
            <h3>Today's Alerts</h3>
            <p className="stat-value">{stats.today_alerts}</p>
          </div>
          <div className="stat-card">
            <h3>Online Cameras</h3>
            <p className="stat-value">{stats.online_cameras} / {stats.total_cameras}</p>
          </div>
        </div>
      )}
      <div className="cameras-section">
        <h2>Cameras</h2>
        <div className="cameras-grid">
          {cameraList.map(camera => (
            <div key={camera.id} className={`camera-card ${camera.status}`}>
              <h4>{camera.name}</h4>
              <p>{camera.location}</p>
              <span className={`status-badge ${camera.status}`}>{camera.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// AlertsPage.js
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { alerts } from '../services/api';
import { format } from 'date-fns';

export function AlertsPage() {
  const [alertList, setAlertList] = useState([]);
  const [filter, setFilter] = useState('new');
  const navigate = useNavigate();

  useEffect(() => {
    loadAlerts();
  }, [filter]);

  const loadAlerts = async () => {
    try {
      const response = await alerts.getAll({ status: filter });
      setAlertList(response.data);
    } catch (err) {
      console.error('Error loading alerts:', err);
    }
  };

  return (
    <div className="alerts-page">
      <h1>Alerts</h1>
      <div className="filters">
        <button onClick={() => setFilter('new')} className={filter === 'new' ? 'active' : ''}>
          New
        </button>
        <button onClick={() => setFilter('in_review')} className={filter === 'in_review' ? 'active' : ''}>
          In Review
        </button>
        <button onClick={() => setFilter(null)} className={filter === null ? 'active' : ''}>
          All
        </button>
      </div>
      <div className="alerts-list">
        {alertList.map(alert => (
          <div
            key={alert.id}
            className={`alert-card severity-${alert.severity}`}
            onClick={() => navigate(`/alerts/${alert.id}`)}
          >
            <div className="alert-header">
              <span className={`severity-badge ${alert.severity}`}>{alert.severity}</span>
              <span className="timestamp">{format(new Date(alert.timestamp), 'yyyy-MM-dd HH:mm:ss')}</span>
            </div>
            <div className="alert-body">
              <p><strong>Camera:</strong> {alert.camera?.name}</p>
              <p><strong>Risk Score:</strong> {alert.risk_score.toFixed(2)}</p>
              <p><strong>Status:</strong> {alert.status}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// AlertDetailPage.js
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { alerts } from '../services/api';
import ReactPlayer from 'react-player';

export function AlertDetailPage() {
  const { alertId } = useParams();
  const navigate = useNavigate();
  const [alert, setAlert] = useState(null);
  const [comment, setComment] = useState('');

  useEffect(() => {
    loadAlert();
  }, [alertId]);

  const loadAlert = async () => {
    try {
      const response = await alerts.getById(alertId);
      setAlert(response.data);
    } catch (err) {
      console.error('Error loading alert:', err);
    }
  };

  const handleDecision = async (decision) => {
    try {
      await alerts.createDecision(alertId, { decision, comment });
      navigate('/alerts');
    } catch (err) {
      console.error('Error creating decision:', err);
    }
  };

  if (!alert) return <div>Loading...</div>;

  return (
    <div className="alert-detail-page">
      <h1>Alert Details</h1>
      <div className="alert-info">
        <p><strong>Camera:</strong> {alert.camera?.name}</p>
        <p><strong>Time:</strong> {new Date(alert.timestamp).toLocaleString()}</p>
        <p><strong>Risk Score:</strong> {alert.risk_score.toFixed(2)}</p>
        <p><strong>Severity:</strong> <span className={`severity-badge ${alert.severity}`}>{alert.severity}</span></p>
      </div>
      {alert.clip_path && (
        <div className="video-player">
          <ReactPlayer
            url={`/clips/${alertId}`}
            controls
            width="100%"
            height="auto"
          />
        </div>
      )}
      <div className="event-summary">
        <h3>Events</h3>
        {alert.event_summary.map((event, idx) => (
          <div key={idx} className="event-item">
            <p><strong>Type:</strong> {event.type}</p>
            <p><strong>Confidence:</strong> {(event.confidence * 100).toFixed(1)}%</p>
          </div>
        ))}
      </div>
      <div className="decision-section">
        <h3>Your Decision</h3>
        <textarea
          placeholder="Add comment..."
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
        <div className="decision-buttons">
          <button className="btn-confirm" onClick={() => handleDecision('confirmed')}>
            ✓ Confirm
          </button>
          <button className="btn-false" onClick={() => handleDecision('false_positive')}>
            ✗ False Positive
          </button>
          <button className="btn-escalate" onClick={() => handleDecision('escalated')}>
            ⚠ Escalate
          </button>
        </div>
      </div>
    </div>
  );
}

// Navbar.js
export function Navbar({ user, onLogout }) {
  return (
    <nav className="navbar">
      <div className="nav-brand">Risk Detection</div>
      <div className="nav-links">
        <a href="/dashboard">Dashboard</a>
        <a href="/alerts">Alerts</a>
        <a href="/cameras">Cameras</a>
        {user.role === 'admin' && <a href="/settings">Settings</a>}
      </div>
      <div className="nav-user">
        <span>{user.username} ({user.role})</span>
        <button onClick={onLogout}>Logout</button>
      </div>
    </nav>
  );
}
