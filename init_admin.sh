#!/bin/bash

echo "=================================================="
echo "Creating Admin User"
echo "=================================================="
echo ""

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 5

# Generate password hash
echo "🔐 Generating password hash..."
HASH=$(docker exec -it risk-engine python -c "import bcrypt; print(bcrypt.hashpw(b'admin123', bcrypt.gensalt(rounds=12)).decode('utf-8'))" | tr -d '\r')

echo "Generated hash: ${HASH:0:20}..."
echo ""

# Create admin user
echo "👤 Creating admin user..."
docker exec -it risk-postgres psql -U riskuser -d risk_detection << SQL
-- Delete existing admin if any
DELETE FROM users WHERE username = 'admin';

-- Create new admin user
INSERT INTO users (username, password_hash, role, full_name, email, active, created_at)
VALUES ('admin', '${HASH}', 'admin', 'Administrator', 'admin@school.com', true, NOW());

-- Verify user was created
SELECT id, username, role, active FROM users WHERE username = 'admin';
SQL

echo ""
echo "✅ Admin user created successfully!"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "You can now login at http://localhost"
