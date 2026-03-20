#!/bin/bash

echo "=================================================="
echo "Testing Login System"
echo "=================================================="
echo ""

# Step 1: Check if containers are running
echo "1️⃣ Checking if containers are running..."
RUNNING=$(docker ps | grep -c "risk-engine\|risk-postgres")

if [ "$RUNNING" -lt 2 ]; then
    echo "❌ Containers are not running!"
    echo "   Please run: docker-compose up -d"
    exit 1
fi
echo "✅ Containers are running"
echo ""

# Step 2: Check database connection
echo "2️⃣ Checking database connection..."
DB_CHECK=$(docker exec risk-postgres pg_isready -U riskuser 2>&1)
if echo "$DB_CHECK" | grep -q "accepting"; then
    echo "✅ Database is ready"
else
    echo "❌ Database is not ready. Wait a few seconds and try again."
    exit 1
fi
echo ""

# Step 3: Check if admin user exists
echo "3️⃣ Checking if admin user exists..."
USER_CHECK=$(docker exec risk-postgres psql -U riskuser -d risk_detection -t -c "SELECT COUNT(*) FROM users WHERE username = 'admin';" 2>/dev/null | tr -d ' ')

if [ "$USER_CHECK" = "1" ]; then
    echo "✅ Admin user exists"
    
    # Show user details
    echo ""
    echo "📋 Admin user details:"
    docker exec risk-postgres psql -U riskuser -d risk_detection -c "SELECT username, role, active, created_at FROM users WHERE username = 'admin';"
else
    echo "❌ Admin user does NOT exist!"
    echo ""
    echo "Creating admin user now..."
    
    # Create admin user using create_admin.py
    docker exec risk-engine python create_admin.py
    
    if [ $? -eq 0 ]; then
        echo "✅ Admin user created successfully"
    else
        echo "❌ Failed to create admin user"
        exit 1
    fi
fi
echo ""

# Step 4: Test login via API
echo "4️⃣ Testing login via API..."
RESPONSE=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin&password=admin123")

if echo "$RESPONSE" | grep -q "access_token"; then
    echo "✅ Login successful!"
    echo ""
    echo "Token received:"
    echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print('   ', data.get('access_token', '')[:50], '...')" 2>/dev/null || echo "   $RESPONSE" | head -c 50
else
    echo "❌ Login failed!"
    echo ""
    echo "Response:"
    echo "$RESPONSE"
    echo ""
    echo "This might be a password hash mismatch. Let's recreate the user..."
    docker exec risk-engine python create_admin.py
fi

echo ""
echo "=================================================="
echo "🌐 Now try logging in at: http://localhost"
echo "   Username: admin"
echo "   Password: admin123"
echo "=================================================="
