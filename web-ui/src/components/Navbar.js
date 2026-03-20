import React from 'react';
import { Link, useLocation } from 'react-router-dom';

function Navbar({ user, onLogout }) {
  const location = useLocation();
  
  const isActive = (path) => location.pathname === path;
  
  const linkStyle = (path) => ({
    padding: '10px 20px',
    textDecoration: 'none',
    color: isActive(path) ? '#667eea' : '#333',
    fontWeight: isActive(path) ? 'bold' : 'normal',
    borderBottom: isActive(path) ? '2px solid #667eea' : 'none'
  });
  
  return (
    <nav style={{
      background: 'white',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      padding: '15px 20px',
      marginBottom: '20px'
    }}>
      <div style={{
        maxWidth: '1200px',
        margin: '0 auto',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '20px' }}>🏫 Risk Detection</h2>
          <Link to="/dashboard" style={linkStyle('/dashboard')}>Dashboard</Link>
          <Link to="/cameras" style={linkStyle('/cameras')}>Cameras</Link>
          <Link to="/alerts" style={linkStyle('/alerts')}>Alerts</Link>
          <Link to="/settings" style={linkStyle('/settings')}>Settings</Link>
        </div>
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
          <span style={{ color: '#666' }}>👤 {user?.name}</span>
          <button
            onClick={onLogout}
            style={{
              padding: '8px 16px',
              background: '#f44336',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
