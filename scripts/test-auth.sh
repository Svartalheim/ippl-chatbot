#!/bin/bash
# Script untuk testing autentikasi Keycloak

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
USERNAME="${USERNAME:-dev}"
PASSWORD="${PASSWORD:-dev}"

echo "🔐 Testing Authentication Flow"
echo "================================"
echo "Base URL: $BASE_URL"
echo "Username: $USERNAME"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Test Login
echo -e "${BLUE}1. Testing Login...${NC}"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")

if echo "$LOGIN_RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Login successful${NC}"
    ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
    REFRESH_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.refresh_token')
    EXPIRES_IN=$(echo "$LOGIN_RESPONSE" | jq -r '.expires_in')
    echo "  Access token expires in: ${EXPIRES_IN}s"
else
    echo -e "${RED}✗ Login failed${NC}"
    echo "$LOGIN_RESPONSE" | jq '.'
    exit 1
fi
echo ""

# 2. Test /me endpoint
echo -e "${BLUE}2. Testing /me endpoint...${NC}"
ME_RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" "$BASE_URL/me")

if echo "$ME_RESPONSE" | jq -e '.username' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ /me endpoint works${NC}"
    echo "$ME_RESPONSE" | jq '{username, email, full_name, roles}'
else
    echo -e "${RED}✗ /me endpoint failed${NC}"
    echo "$ME_RESPONSE" | jq '.'
    exit 1
fi
echo ""

# 3. Test protected endpoint without token
echo -e "${BLUE}3. Testing protected endpoint without token...${NC}"
NO_TOKEN_RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/me")
HTTP_CODE=$(echo "$NO_TOKEN_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✓ Correctly returns 401 Unauthorized${NC}"
else
    echo -e "${RED}✗ Expected 401, got $HTTP_CODE${NC}"
fi
echo ""

# 4. Test token introspection
echo -e "${BLUE}4. Testing token introspection...${NC}"
INTROSPECT_RESPONSE=$(curl -s "$BASE_URL/auth/introspect?token=$ACCESS_TOKEN")

if echo "$INTROSPECT_RESPONSE" | jq -e '.active' > /dev/null 2>&1; then
    ACTIVE=$(echo "$INTROSPECT_RESPONSE" | jq -r '.active')
    if [ "$ACTIVE" = "true" ]; then
        echo -e "${GREEN}✓ Token is active${NC}"
        echo "  Username: $(echo "$INTROSPECT_RESPONSE" | jq -r '.preferred_username')"
        echo "  Issued at: $(date -r $(echo "$INTROSPECT_RESPONSE" | jq -r '.iat') 2>/dev/null || echo 'N/A')"
        echo "  Expires at: $(date -r $(echo "$INTROSPECT_RESPONSE" | jq -r '.exp') 2>/dev/null || echo 'N/A')"
    else
        echo -e "${YELLOW}⚠ Token is not active${NC}"
    fi
else
    echo -e "${RED}✗ Introspection failed${NC}"
    echo "$INTROSPECT_RESPONSE" | jq '.'
fi
echo ""

# 5. Test LLM chat endpoint
echo -e "${BLUE}5. Testing LLM chat endpoint...${NC}"
CHAT_RESPONSE=$(curl -s -X POST "$BASE_URL/llm/chat" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello, siapa kamu?"}')

if echo "$CHAT_RESPONSE" | jq -e '.answer' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Chat endpoint works${NC}"
    echo "  User: $(echo "$CHAT_RESPONSE" | jq -r '.user')"
    echo "  Answer: $(echo "$CHAT_RESPONSE" | jq -r '.answer' | head -c 100)..."
else
    echo -e "${YELLOW}⚠ Chat endpoint failed (Ollama might not be ready)${NC}"
    echo "$CHAT_RESPONSE" | jq '.' || echo "$CHAT_RESPONSE"
fi
echo ""

# 6. Test token refresh
echo -e "${BLUE}6. Testing token refresh...${NC}"
REFRESH_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}")

if echo "$REFRESH_RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Token refresh works${NC}"
    NEW_ACCESS_TOKEN=$(echo "$REFRESH_RESPONSE" | jq -r '.access_token')
    NEW_REFRESH_TOKEN=$(echo "$REFRESH_RESPONSE" | jq -r '.refresh_token')
    echo "  New access token obtained"
else
    echo -e "${RED}✗ Token refresh failed${NC}"
    echo "$REFRESH_RESPONSE" | jq '.'
    exit 1
fi
echo ""

# 7. Test logout
echo -e "${BLUE}7. Testing logout...${NC}"
LOGOUT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/auth/logout" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$NEW_REFRESH_TOKEN\"}")
HTTP_CODE=$(echo "$LOGOUT_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "204" ] || [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Logout successful${NC}"
else
    echo -e "${YELLOW}⚠ Logout returned $HTTP_CODE (might be ok)${NC}"
fi
echo ""

# 8. Test using refresh token after logout (should fail)
echo -e "${BLUE}8. Testing refresh with revoked token...${NC}"
REVOKED_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$NEW_REFRESH_TOKEN\"}")
HTTP_CODE=$(echo "$REVOKED_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✓ Correctly rejects revoked refresh token${NC}"
else
    echo -e "${YELLOW}⚠ Expected 401, got $HTTP_CODE (token might still be valid)${NC}"
fi
echo ""

# Summary
echo "================================"
echo -e "${GREEN}✅ Authentication tests completed!${NC}"
echo ""
echo "📝 Quick Commands:"
echo ""
echo "# Login and save token"
echo "TOKEN=\$(curl -s -X POST $BASE_URL/auth/login \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}' | jq -r .access_token)"
echo ""
echo "# Get user info"
echo "curl -H \"Authorization: Bearer \$TOKEN\" $BASE_URL/me | jq"
echo ""
echo "# Chat with LLM"
echo "curl -X POST $BASE_URL/llm/chat \\"
echo "  -H \"Authorization: Bearer \$TOKEN\" \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"prompt\":\"Halo!\"}' | jq"
