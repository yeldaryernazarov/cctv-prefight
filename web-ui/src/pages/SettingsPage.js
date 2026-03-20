import React, { useState, useEffect } from 'react';
import { config } from '../services/api';

function SettingsPage() {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await config.get();
      setSettings(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching settings:', error);
      setMessage({ type: 'error', text: 'Failed to load settings' });
      setLoading(false);
    }
  };

  const handleSave = async (key, value) => {
    setSaving(true);
    try {
      await config.update(key, parseFloat(value));
      setMessage({ type: 'success', text: `${key} updated successfully!` });
      setTimeout(() => setMessage(null), 3000);
    } catch (error) {
      console.error('Error saving setting:', error);
      setMessage({ type: 'error', text: `Failed to update ${key}` });
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <div style={{ fontSize: '18px', color: '#666' }}>Loading settings...</div>
      </div>
    );
  }

  return (
    <div style={{ 
      padding: '30px',
      maxWidth: '1200px',
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
        <h1 style={{ 
          fontSize: '32px',
          marginBottom: '10px',
          color: '#333',
          display: 'flex',
          alignItems: 'center',
          gap: '15px'
        }}>
          ⚙️ Risk Detection Settings
        </h1>
        <p style={{ color: '#666', marginBottom: '40px', fontSize: '16px' }}>
          Configure thresholds and parameters for the AI-powered risk detection system
        </p>

        {/* Message */}
        {message && (
          <div style={{
            padding: '15px 20px',
            marginBottom: '30px',
            borderRadius: '8px',
            background: message.type === 'success' ? '#d4edda' : '#f8d7da',
            color: message.type === 'success' ? '#155724' : '#721c24',
            border: `1px solid ${message.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`,
            display: 'flex',
            alignItems: 'center',
            gap: '10px'
          }}>
            <span style={{ fontSize: '20px' }}>
              {message.type === 'success' ? '✓' : '✗'}
            </span>
            {message.text}
          </div>
        )}

        {/* Settings Sections */}
        <div style={{ display: 'grid', gap: '30px' }}>
          
          {/* Alert Thresholds */}
          <Section title="🚨 Alert Thresholds" description="Configure when alerts are created based on risk scores">
            <SettingItem
              label="Alert Threshold"
              description="Minimum risk score to create an alert (recommended: 15.0)"
              value={settings.risk_score_alert_threshold || 10.0}
              min={5}
              max={30}
              step={0.5}
              unit="points"
              onChange={(v) => handleChange('risk_score_alert_threshold', v)}
              onSave={() => handleSave('risk_score_alert_threshold', settings.risk_score_alert_threshold)}
              saving={saving}
              color="#ff9800"
            />
            
            <SettingItem
              label="Critical Threshold"
              description="Risk score for CRITICAL alerts requiring immediate action (recommended: 20.0)"
              value={settings.risk_score_critical_threshold || 20.0}
              min={15}
              max={50}
              step={0.5}
              unit="points"
              onChange={(v) => handleChange('risk_score_critical_threshold', v)}
              onSave={() => handleSave('risk_score_critical_threshold', settings.risk_score_critical_threshold)}
              saving={saving}
              color="#f44336"
            />
          </Section>

          {/* Event Aggregation */}
          <Section title="⏱️ Event Aggregation" description="Control how events are grouped together">
            <SettingItem
              label="Aggregation Window"
              description="Time window to collect events before calculating risk (recommended: 60 seconds)"
              value={settings.aggregation_window_seconds || 20}
              min={10}
              max={180}
              step={5}
              unit="seconds"
              onChange={(v) => handleChange('aggregation_window_seconds', v)}
              onSave={() => handleSave('aggregation_window_seconds', settings.aggregation_window_seconds)}
              saving={saving}
              color="#2196F3"
            />
            
            <SettingItem
              label="Cooldown Period"
              description="Wait time before creating another alert for the same camera (recommended: 180 seconds)"
              value={settings.cooldown_seconds || 30}
              min={30}
              max={600}
              step={30}
              unit="seconds"
              onChange={(v) => handleChange('cooldown_seconds', v)}
              onSave={() => handleSave('cooldown_seconds', settings.cooldown_seconds)}
              saving={saving}
              color="#4CAF50"
            />
          </Section>

          {/* Info Box */}
          <div style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            padding: '25px',
            borderRadius: '12px',
            color: 'white'
          }}>
            <h3 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
              💡 How It Works
            </h3>
            <ul style={{ lineHeight: '1.8', paddingLeft: '20px' }}>
              <li><strong>Events</strong> are detected by AI cameras (fighting, running, crowds, etc.)</li>
              <li><strong>Risk Score</strong> = sum of (event weight × confidence × duration factor)</li>
              <li><strong>Alert</strong> is created when risk score exceeds the threshold</li>
              <li><strong>Severity</strong>: Critical (≥{settings.risk_score_critical_threshold || 20}) → High (≥{settings.risk_score_alert_threshold || 15}) → Medium</li>
              <li><strong>Cooldown</strong> prevents alert spam from the same camera</li>
            </ul>
          </div>

          {/* Quick Presets */}
          <Section title="🎯 Quick Presets" description="Apply recommended configurations">
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
              gap: '15px'
            }}>
              <PresetButton
                title="🔴 High Sensitivity"
                description="More alerts, faster response"
                settings={{
                  risk_score_alert_threshold: 10.0,
                  risk_score_critical_threshold: 15.0,
                  aggregation_window_seconds: 30,
                  cooldown_seconds: 60
                }}
                onApply={(s) => setSettings(prev => ({ ...prev, ...s }))}
              />
              
              <PresetButton
                title="⚖️ Balanced (Default)"
                description="Recommended for most schools"
                settings={{
                  risk_score_alert_threshold: 15.0,
                  risk_score_critical_threshold: 20.0,
                  aggregation_window_seconds: 60,
                  cooldown_seconds: 180
                }}
                onApply={(s) => setSettings(prev => ({ ...prev, ...s }))}
              />
              
              <PresetButton
                title="🟢 Low Sensitivity"
                description="Fewer alerts, high confidence only"
                settings={{
                  risk_score_alert_threshold: 20.0,
                  risk_score_critical_threshold: 30.0,
                  aggregation_window_seconds: 90,
                  cooldown_seconds: 300
                }}
                onApply={(s) => setSettings(prev => ({ ...prev, ...s }))}
              />
            </div>
            
            <button
              onClick={async () => {
                setSaving(true);
                try {
                  await Promise.all([
                    config.update('risk_score_alert_threshold', parseFloat(settings.risk_score_alert_threshold)),
                    config.update('risk_score_critical_threshold', parseFloat(settings.risk_score_critical_threshold)),
                    config.update('aggregation_window_seconds', parseFloat(settings.aggregation_window_seconds)),
                    config.update('cooldown_seconds', parseFloat(settings.cooldown_seconds))
                  ]);
                  setMessage({ type: 'success', text: 'All settings saved successfully!' });
                  setTimeout(() => setMessage(null), 3000);
                } catch (error) {
                  setMessage({ type: 'error', text: 'Failed to save some settings' });
                } finally {
                  setSaving(false);
                }
              }}
              disabled={saving}
              style={{
                marginTop: '20px',
                width: '100%',
                padding: '15px',
                background: saving ? '#ccc' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: saving ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 15px rgba(0,0,0,0.2)',
                transition: 'all 0.3s'
              }}
            >
              {saving ? '⏳ Saving All Settings...' : '💾 Save All Settings'}
            </button>
          </Section>
        </div>
      </div>
    </div>
  );
}

function Section({ title, description, children }) {
  return (
    <div style={{
      border: '2px solid #e0e0e0',
      borderRadius: '12px',
      padding: '25px',
      background: '#fafafa'
    }}>
      <h2 style={{ marginTop: 0, fontSize: '22px', color: '#333' }}>{title}</h2>
      <p style={{ color: '#666', marginBottom: '25px' }}>{description}</p>
      <div style={{ display: 'grid', gap: '20px' }}>
        {children}
      </div>
    </div>
  );
}

function SettingItem({ label, description, value, min, max, step, unit, onChange, onSave, saving, color }) {
  return (
    <div style={{
      background: 'white',
      padding: '20px',
      borderRadius: '8px',
      border: '1px solid #e0e0e0'
    }}>
      <div style={{ marginBottom: '15px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
          <label style={{ fontWeight: 'bold', fontSize: '16px', color: '#333' }}>
            {label}
          </label>
          <span style={{
            fontSize: '24px',
            fontWeight: 'bold',
            color: color,
            minWidth: '100px',
            textAlign: 'right'
          }}>
            {value} {unit}
          </span>
        </div>
        <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#666' }}>
          {description}
        </p>
      </div>

      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: '100%',
          height: '8px',
          borderRadius: '5px',
          background: `linear-gradient(to right, ${color} 0%, ${color} ${((value - min) / (max - min)) * 100}%, #ddd ${((value - min) / (max - min)) * 100}%, #ddd 100%)`,
          outline: 'none',
          cursor: 'pointer'
        }}
      />

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '10px', fontSize: '12px', color: '#999' }}>
        <span>{min} {unit}</span>
        <span>{max} {unit}</span>
      </div>

      <button
        onClick={onSave}
        disabled={saving}
        style={{
          marginTop: '15px',
          width: '100%',
          padding: '10px',
          background: saving ? '#ccc' : color,
          color: 'white',
          border: 'none',
          borderRadius: '5px',
          cursor: saving ? 'not-allowed' : 'pointer',
          fontWeight: 'bold',
          transition: 'all 0.2s'
        }}
      >
        {saving ? 'Saving...' : 'Save'}
      </button>
    </div>
  );
}

function PresetButton({ title, description, settings, onApply }) {
  return (
    <button
      onClick={() => onApply(settings)}
      style={{
        padding: '20px',
        background: 'white',
        border: '2px solid #e0e0e0',
        borderRadius: '8px',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'all 0.3s'
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.border = '2px solid #667eea';
        e.currentTarget.style.boxShadow = '0 4px 15px rgba(102, 126, 234, 0.3)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.border = '2px solid #e0e0e0';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '8px' }}>
        {title}
      </div>
      <div style={{ fontSize: '14px', color: '#666' }}>
        {description}
      </div>
    </button>
  );
}

export default SettingsPage;
