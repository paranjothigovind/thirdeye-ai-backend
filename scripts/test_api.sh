#!/bin/bash
# Test API endpoints

set -e

API_URL="${API_URL:-http://localhost:8000}"

echo "🧪 Testing Third Eye Chatbot API at $API_URL"
echo ""

# Test health endpoint
echo "1️⃣ Testing health endpoint..."
curl -s "$API_URL/api/health" | jq .
echo ""

# Test readiness endpoint
echo "2️⃣ Testing readiness endpoint..."
curl -s "$API_URL/api/ready" | jq .
echo ""

# Test chat endpoint
echo "3️⃣ Testing chat endpoint..."
curl -s -X POST "$API_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the Third Eye chakra?"}
    ],
    "stream": false
  }' | jq .
echo ""

# Test chat with streaming
echo "4️⃣ Testing streaming chat..."
curl -N -X POST "$API_URL/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "How do I practice Trataka safely?"}
    ],
    "stream": true
  }'
echo ""

echo "✅ API tests completed!"