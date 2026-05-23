$env:ACCESS_MCP_API_KEY = 'test-key-123'
$env:ACCESS_MCP_ALLOWED_DIRS = 'C:\Users\MetalbolicX'
python -c "from ms_access_mcp.mcp.server import run_http; run_http(host='0.0.0.0', port=8000)"
