#!/bin/bash

echo "=================================================="
echo "School Risk Detection - Quick Setup"
echo "=================================================="
echo ""

echo "⏳ Waiting for services to start (10 seconds)..."
sleep 10

# Step 1: Create admin user
echo ""
echo "👤 Step 1: Creating admin user..."
HASH=$(docker exec risk-engine python -c "import bcrypt; print(bcrypt.hashpw(b'admin123', bcrypt.gensalt(rounds=12)).decode('utf-8'))" 2>/dev/null | tr -d '\r')

if [ -z "$HASH" ]; then
    echo "❌ Failed to generate password hash"
    echo "Make sure risk-engine container is running!"
    exit 1
fi

docker exec risk-postgres psql -U riskuser -d risk_detection << SQL
-- Delete existing admin
DELETE FROM users WHERE username = 'admin';

-- Create admin user
INSERT INTO users (username, password_hash, role, full_name, email, active, created_at)
VALUES ('admin', '${HASH}', 'admin', 'Administrator', 'admin@school.com', true, NOW());

-- Show created user
SELECT username, role, active, created_at FROM users WHERE username = 'admin';
SQL

# Step 2: Update system settings
echo ""
echo "⚙️ Step 2: Configuring risk detection settings..."
docker exec risk-postgres psql -U riskuser -d risk_detection << SQL
-- Update risk thresholds
UPDATE system_config SET value = '15.0' WHERE key = 'risk_score_alert_threshold';
UPDATE system_config SET value = '20.0' WHERE key = 'risk_score_critical_threshold';
UPDATE system_config SET value = '60' WHERE key = 'aggregation_window_seconds';
UPDATE system_config SET value = '180' WHERE key = 'cooldown_seconds';

-- Show current settings
SELECT key, value, description FROM system_config 
WHERE key IN ('risk_score_alert_threshold', 'risk_score_critical_threshold', 'aggregation_window_seconds', 'cooldown_seconds')
ORDER BY key;
SQL

# Step 3: Set cameras online
echo ""
echo "📹 Step 3: Updating camera status..."
docker exec risk-postgres psql -U riskuser -d risk_detection << SQL
UPDATE cameras SET status = 'online', last_seen = NOW();

SELECT name, location, status, last_seen FROM cameras;
SQL

# Step 4: Add event types for early warning
echo ""
echo "🎯 Step 4: Adding risk event types..."
docker exec risk-postgres psql -U riskuser -d risk_detection << SQL
-- Add additional event types
INSERT INTO risk_event_types (id, name, description, base_weight, enabled, config)
VALUES 
  ('aggressive_posture', 'Aggressive Posture', 'Агрессивная поза/жесты', 4.0, true, '{}'::jsonb),
  ('face_to_face', 'Face-to-Face Confrontation', 'Конфронтация лицом к лицу', 6.0, true, '{}'::jsonb),
  ('raised_voice', 'Raised Voice', 'Повышенные голоса', 3.5, true, '{}'::jsonb),
  ('sudden_movement', 'Sudden Movement', 'Резкие движения', 3.5, true, '{}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- Show all event types
SELECT id, name, base_weight, enabled FROM risk_event_types ORDER BY base_weight DESC;
SQL

echo ""
echo "=================================================="
echo "✅ Setup Complete!"
echo "=================================================="
echo ""
echo "🎉 Your School Risk Detection system is ready!"
echo ""
echo "📝 Login Credentials:"
echo "   URL:      http://localhost"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "⚙️ Current Settings:"
echo "   Alert Threshold:    15.0 points"
echo "   Critical Threshold: 20.0 points"
echo "   Aggregation Window: 60 seconds"
echo "   Cooldown Period:    180 seconds"
echo ""
echo "💡 Next Steps:"
echo "   1. Open http://localhost in your browser"
echo "   2. Login with admin/admin123"
echo "   3. Go to Settings to adjust thresholds"
echo "   4. Monitor the Dashboard for alerts"
echo ""
