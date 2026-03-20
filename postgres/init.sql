-- PostgreSQL initialization script for Risk Detection MVP

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Cameras table
CREATE TABLE cameras (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    rtsp_url TEXT NOT NULL,
    rtsp_substream_url TEXT,
    location VARCHAR(255),
    status VARCHAR(50) DEFAULT 'offline',
    fps INTEGER DEFAULT 15,
    resolution VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP,
    meta_data JSONB DEFAULT '{}'::jsonb
);

-- Zones/ROI table
CREATE TABLE zones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    polygon JSONB NOT NULL, -- Array of points [{x, y}, ...]
    zone_type VARCHAR(50), -- 'corridor', 'classroom', 'cafeteria', 'entrance'
    schedule_profile VARCHAR(50) DEFAULT 'default', -- 'quiet', 'break', 'lesson'
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB DEFAULT '{}'::jsonb
);

-- Risk event types configuration
CREATE TABLE risk_event_types (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    base_weight FLOAT DEFAULT 1.0,
    enabled BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}'::jsonb -- Thresholds and parameters
);

-- Insert default event types
INSERT INTO risk_event_types (id, name, description, base_weight, config) VALUES
('PROXIMITY_RISK', 'Close Proximity / Rapid Approach', 'Two people rapidly approaching each other or staying too close', 2.0, 
 '{"distance_threshold": 1.5, "duration_min_sec": 2, "rapid_approach_percent": 50}'::jsonb),
('CROWD_RISK', 'Crowd Formation / High Density', 'Multiple people forming dense groups', 3.0,
 '{"min_count": 5, "density_threshold": 0.3, "area_threshold": 100}'::jsonb),
('KINETIC_RISK', 'High Kinetic Activity', 'Rapid movements or acceleration detected', 2.5,
 '{"acceleration_threshold": 5.0, "duration_min_sec": 1.5}'::jsonb),
('CONFRONTATION_RISK', 'Confrontation Stance', 'People facing each other at close distance with tense body language', 4.0,
 '{"distance_threshold": 2.0, "angle_threshold": 45, "duration_min_sec": 3}'::jsonb),
('AGGRESSIVE_MOTION', 'Aggressive Motion Pattern', 'Sudden jerky movements or gestures indicating aggression', 3.5,
 '{"jerk_threshold": 8.0, "min_events": 2}'::jsonb),
('VIOLENCE_POSE_RISK', 'Violence (Pose)', 'Violence classification based on pose keypoints over time', 10.0,
 '{"violence_threshold": 0.7, "cooldown_sec": 10.0}'::jsonb),
('PROFANITY_RISK', 'Profanity / Swear Words', 'Profanity keywords detected from OCR text stream', 6.0,
 '{"event_cooldown_sec": 30.0, "min_keywords_found": 1}'::jsonb);

-- Risk events (raw detections from analytics)
CREATE TABLE risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    event_type VARCHAR(50) REFERENCES risk_event_types(id),
    timestamp TIMESTAMP NOT NULL,
    confidence FLOAT DEFAULT 0.0,
    duration_seconds FLOAT,
    involved_track_ids INTEGER[],
    meta_data JSONB DEFAULT '{}'::jsonb, -- Additional event data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_risk_events_camera_time ON risk_events(camera_id, timestamp DESC);
CREATE INDEX idx_risk_events_type ON risk_events(event_type);

-- Alerts (aggregated risk events)
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
    zone_id UUID REFERENCES zones(id) ON DELETE SET NULL,
    timestamp TIMESTAMP NOT NULL,
    risk_score FLOAT NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    status VARCHAR(50) DEFAULT 'new', -- 'new', 'in_review', 'confirmed', 'false_positive', 'escalated', 'closed'
    clip_path TEXT,
    clip_start_time TIMESTAMP,
    clip_end_time TIMESTAMP,
    event_summary JSONB DEFAULT '[]'::jsonb, -- Array of contributing events
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_alerts_camera_time ON alerts(camera_id, timestamp DESC);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_severity ON alerts(severity);

-- Alert decisions (human-in-the-loop)
CREATE TABLE alert_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID REFERENCES alerts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL, -- Reference to users table
    decision VARCHAR(50) NOT NULL, -- 'confirmed', 'false_positive', 'escalated'
    comment TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) NOT NULL, -- 'guard', 'admin', 'auditor'
    full_name VARCHAR(255),
    email VARCHAR(255),
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Insert default admin user (password: admin123 - should be changed!)
INSERT INTO users (username, password_hash, role, full_name, email) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqNQqAEqyW', 'admin', 'System Administrator', 'admin@school.local'),
('guard1', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqNQqAEqyW', 'guard', 'Guard User', 'guard@school.local');

-- Audit log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    details JSONB DEFAULT '{}'::jsonb,
    ip_address INET,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_user ON audit_log(user_id, timestamp DESC);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);

-- System configuration
CREATE TABLE system_config (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL
);

-- Insert default configuration
INSERT INTO system_config (key, value, description) VALUES
('aggregation_window_seconds', '60', 'Time window for event aggregation (increased for better grouping)'),
('risk_score_alert_threshold', '15.0', 'Minimum risk score to generate alert (increased to reduce false alerts)'),
('risk_score_critical_threshold', '25.0', 'Risk score for critical alerts'),
('cooldown_seconds', '180', 'Cooldown period between alerts for same zone (3 minutes)'),
('clip_retention_days', '14', 'Number of days to keep event clips'),
('clip_pre_seconds', '10', 'Seconds before event to include in clip'),
('clip_post_seconds', '10', 'Seconds after event to include in clip'),
('max_cameras_per_server', '8', 'Maximum cameras per edge server');

-- Camera statistics (for monitoring)
CREATE TABLE camera_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id UUID REFERENCES cameras(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    fps FLOAT,
    dropped_frames INTEGER,
    people_count INTEGER,
    gpu_util_percent FLOAT,
    latency_ms FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_camera_stats_camera_time ON camera_stats(camera_id, timestamp DESC);

-- Cleanup function for old clips (called by retention policy)
CREATE OR REPLACE FUNCTION cleanup_old_clips()
RETURNS void AS $$
DECLARE
    retention_days INTEGER;
BEGIN
    SELECT (value::text)::integer INTO retention_days 
    FROM system_config WHERE key = 'clip_retention_days';
    
    DELETE FROM alerts 
    WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL;
    
    DELETE FROM risk_events 
    WHERE created_at < NOW() - ((retention_days + 7) || ' days')::INTERVAL;
    
    DELETE FROM camera_stats 
    WHERE created_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Create views for common queries
CREATE VIEW active_alerts AS
SELECT 
    a.*,
    c.name as camera_name,
    c.location as camera_location,
    z.name as zone_name,
    COUNT(ad.id) as decision_count
FROM alerts a
LEFT JOIN cameras c ON a.camera_id = c.id
LEFT JOIN zones z ON a.zone_id = z.id
LEFT JOIN alert_decisions ad ON a.id = ad.alert_id
WHERE a.status IN ('new', 'in_review')
GROUP BY a.id, c.name, c.location, z.name;

CREATE VIEW alert_statistics AS
SELECT 
    camera_id,
    DATE_TRUNC('day', timestamp) as day,
    COUNT(*) as total_alerts,
    COUNT(*) FILTER (WHERE severity = 'critical') as critical_count,
    COUNT(*) FILTER (WHERE severity = 'high') as high_count,
    COUNT(*) FILTER (WHERE status = 'confirmed') as confirmed_count,
    COUNT(*) FILTER (WHERE status = 'false_positive') as false_positive_count,
    AVG(risk_score) as avg_risk_score
FROM alerts
GROUP BY camera_id, DATE_TRUNC('day', timestamp);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO riskuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO riskuser;
