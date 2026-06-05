# Environment variables can be set here or in a .env file at the project root.
# .env is already in .gitignore — safe for secrets.
#
# Example .env:
#   PGPASSWORD=mysecretpassword
#   ACCESS_MCP_API_KEY=test-key-123
#   ACCESS_MCP_ALLOWED_DIRS=C:\Users\MetalbolicX

$env:ACCESS_MCP_API_KEY = 'test-key-123'
$env:ACCESS_MCP_ALLOWED_DIRS = 'C:\Users\MetalbolicX'
python -c "from ms_access_mcp.mcp.server import run_http; run_http(host='0.0.0.0', port=8000)"
