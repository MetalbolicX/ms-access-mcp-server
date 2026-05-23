#!/bin/bash
# COM Thread Affinity Integration Test
set -euo pipefail

BASE_URL="http://172.19.208.1:8000/mcp"
API_KEY="test-key-123"
DBPATH="C:\\\\Users\\\\MetalbolicX\\\\test-helper.accdb"
ITERATIONS=3
FAILURES=0
PASSES=0
CURL_OPTS=(-s --connect-timeout 5 -m 60)

HEADERS=(-H "Authorization: Bearer $API_KEY" -H "Accept: application/json, text/event-stream" -H "Content-Type: application/json")

echo "============================================"
echo "COM Thread Affinity Integration Test"
echo "============================================"
echo "Server : $BASE_URL"
echo "DB     : $DBPATH"
echo "Cycles : $ITERATIONS"
echo ""

# Health check
echo "--- Health check ---"
INIT=$(curl "${CURL_OPTS[@]}" -D - -X POST "$BASE_URL" "${HEADERS[@]}" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0"}}}')
SID=$(echo "$INIT" | grep -i 'mcp-session-id' | head -1 | awk -F': ' '{print $2}' | tr -d '\r\n')
echo "Session: $SID"
TOOLS=$(curl "${CURL_OPTS[@]}" -X POST "$BASE_URL" "${HEADERS[@]}" -H "mcp-session-id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}')
if echo "$TOOLS" | grep -q '"result"'; then echo "Server OK"; else echo "Server FAILED"; exit 1; fi

# Main test loop
for ((i=1; i<=ITERATIONS; i++)); do
  echo ""
  echo "--- Iteration $i/$ITERATIONS ---"

  # Fresh initialization
  INIT=$(curl "${CURL_OPTS[@]}" -D - -X POST "$BASE_URL" "${HEADERS[@]}" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0"}}}')
  SID=$(echo "$INIT" | grep -i 'mcp-session-id' | head -1 | awk -F': ' '{print $2}' | tr -d '\r\n')
  sleep 0.5

  STEP=1

  # 1. connect_access
  echo -n "  [$STEP/4] connect_access... "
  RESP=$(curl "${CURL_OPTS[@]}" -X POST "$BASE_URL" "${HEADERS[@]}" -H "mcp-session-id: $SID" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"connect_access\",\"arguments\":{\"database_path\":\"${DBPATH}\",\"use_com\":true}}}")
  if echo "$RESP" | grep -q '"connected":true'; then
    echo "OK"
  else
    ERR=$(echo "$RESP" | grep -o '"error":"[^"]*"' | head -1)
    echo "FAIL: $ERR"
    echo "$RESP" | head -3
    FAILURES=$((FAILURES + 1)); continue
  fi
  STEP=$((STEP + 1))

  # 2. get_tables (COM thread affinity test)
  echo -n "  [$STEP/4] get_tables... "
  RESP=$(curl "${CURL_OPTS[@]}" -X POST "$BASE_URL" "${HEADERS[@]}" -H "mcp-session-id: $SID" \
    -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_tables","arguments":{}}}')
  if echo "$RESP" | grep -qi 'not connected'; then
    echo "FAIL: 'Not connected'!"
    FAILURES=$((FAILURES + 1)); continue
  elif echo "$RESP" | grep -q '"tables"'; then
    TABLE_COUNT=$(echo "$RESP" | grep -o 'table_name' | wc -l)
    echo "OK ($TABLE_COUNT tables)"
  elif echo "$RESP" | grep -q '"error"'; then
    ERR=$(echo "$RESP" | grep -o '"message":"[^"]*"')
    echo "FAIL: $ERR"
    FAILURES=$((FAILURES + 1)); continue
  else
    echo "OK"
  fi
  STEP=$((STEP + 1))

  # 3. get_relationships (another COM operation)
  echo -n "  [$STEP/4] get_relationships... "
  RESP=$(curl "${CURL_OPTS[@]}" -X POST "$BASE_URL" "${HEADERS[@]}" -H "mcp-session-id: $SID" \
    -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"get_relationships","arguments":{}}}')
  if echo "$RESP" | grep -qi 'not connected'; then
    echo "FAIL: 'Not connected'!"
    FAILURES=$((FAILURES + 1)); continue
  elif echo "$RESP" | grep -q '"error"'; then
    ERR=$(echo "$RESP" | grep -o '"message":"[^"]*"')
    echo "WARN: $ERR"
  else
    echo "OK"
  fi
  STEP=$((STEP + 1))

  # 4. disconnect
  echo -n "  [$STEP/4] disconnect_access... "
  RESP=$(curl "${CURL_OPTS[@]}" -X POST "$BASE_URL" "${HEADERS[@]}" -H "mcp-session-id: $SID" \
    -d '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"disconnect_access","arguments":{}}}')
  if echo "$RESP" | grep -q '"error"'; then
    echo "WARN"
  else
    echo "OK"
  fi

  PASSES=$((PASSES + 1))
done

echo ""
echo "============================================"
if [ "$FAILURES" -eq 0 ]; then
  echo "RESULT: ALL $PASSES/$ITERATIONS ITERATIONS PASSED"
  echo "No 'Not connected' errors detected."
  exit 0
else
  echo "RESULT: $FAILURES FAILURES, $PASSES PASSED"
  exit 1
fi
