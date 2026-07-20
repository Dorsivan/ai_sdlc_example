#!/bin/bash
# Quick test script to verify authentication headers are sent correctly

set -e

VLLM_URL="${1:-http://localhost:8080}"
API_KEY="${2:-test-key-12345}"

echo "Testing load_tester.py authentication..."
echo "URL: $VLLM_URL"
echo "API Key: ${API_KEY:0:10}..." # Show only first 10 chars
echo ""

# Test with API key
echo "Running test with --api-key flag..."
python3 load_tester.py \
  --url "$VLLM_URL" \
  --api-key "$API_KEY" \
  --requests 1 \
  --concurrency 1 \
  --prompt-length 100 \
  --max-tokens 10

echo ""
echo "✅ Test completed!"
echo ""
echo "The load tester sends the API key as: Authorization: Bearer $API_KEY"
echo "Check your vLLM logs to verify the header was received."
