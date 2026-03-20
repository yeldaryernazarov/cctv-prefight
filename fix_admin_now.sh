#!/bin/bash

echo "=================================================="
echo "🔧 Quick Fix - Creating Admin User"
echo "=================================================="
echo ""

echo "Generating password hash directly in container..."

# Generate hash using bcrypt directly
HASH=$(docker exec risk-engine python3 -c "
import bcrypt
password = b'admin123'
hash_bytes = bcrypt.hashpw(password, bcrypt.gensalt(rounds=12))
print(hash_bytes.decode('utf-8'))
" 2>/dev/null | tr -d '\r\n')

if [ -z "$HASH" ]; then
    echo "❌ Failed to generate hash"
    exit 1
fi

echo "✅ Hash generated: ${HASH:0:30}..."
echo ""

# Insert into database
echo "Creating admin user in database..."
docker exec risk-postgres psql -U riskuser -d risk_detection << SQL
-- Delete old admin
DELETE FROM users WHERE username = 'admin';

-- Insert new admin with bcrypt hash
INSERT INTO users (username, password_hash, role, full_name, email, active, created_at)
VALUES ('admin', '${HASH}', 'admin', 'Administrator', 'admin@school.com', true, NOW());

-- Verify
SELECT username, role, active, 
       substring(password_hash, 1, 30) as hash_preview,
       created_at 
FROM users WHERE username = 'admin';
SQL

echo ""
echo "Testing login..."
RESPONSE=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin&password=admin123")

if echo "$RESPONSE" | grep -q "access_token"; then
    echo "✅ SUCCESS! Login works!"
    echo ""
    TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'][:50])" 2>/dev/null)
    echo "Token: ${TOKEN}..."
else
    echo "❌ Login still failed"
    echo "Response: $RESPONSE"
    exit 1
fi

echo ""
echo "=================================================="
echo "✅ Admin user is ready!"
echo "=================================================="
echo ""
echo "🌐 Login at: http://localhost"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
