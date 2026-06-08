# MS Access MCP Server - Test Startup Script
#
# Environment variables for test execution.
# Generate a test key with: python -c "import secrets; print(secrets.token_urlsafe(32))"

# Prompt for API key if not set
if (-not $env:ACCESS_MCP_API_KEY) {
    Write-Host "ACCESS_MCP_API_KEY is not set. Using a generated key for testing." -ForegroundColor Yellow
    $env:ACCESS_MCP_API_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
}

# Set allowed directories to user home if not specified
if (-not $env:ACCESS_MCP_ALLOWED_DIRS) {
    $env:ACCESS_MCP_ALLOWED_DIRS = $env:USERPROFILE
}

$env:PYTHONUNBUFFERED = "1"
python -u -c "from ms_access_mcp.mcp.server import run_http; run_http(host='127.0.0.1', port=8000)"