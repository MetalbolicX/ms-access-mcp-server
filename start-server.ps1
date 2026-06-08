# MS Access MCP Server - Startup Script
#
# This script sets environment variables and starts the MCP server.
# Set ACCESS_MCP_API_KEY to a secure random value (>= 32 chars, high entropy).
# Generate a suitable key with:
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
#
# Example:
#   $env:ACCESS_MCP_API_KEY = "your-32-char-minimum-high-entropy-key-here"
#   $env:ACCESS_MCP_ALLOWED_DIRS = "C:\path\to\allowed\directory"

# Prompt for API key if not set
if (-not $env:ACCESS_MCP_API_KEY) {
    Write-Host "ACCESS_MCP_API_KEY is not set. Please enter a secure API key (>= 32 chars):" -ForegroundColor Yellow
    $key = Read-Host -AsSecureString
    $env:ACCESS_MCP_API_KEY = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($key))
}

# Set allowed directories (optional - defaults to user home directory)
if (-not $env:ACCESS_MCP_ALLOWED_DIRS) {
    $env:ACCESS_MCP_ALLOWED_DIRS = $HOME
}

# Start the server on localhost (secure default - not exposed to network)
python -c "from ms_access_mcp.mcp.server import run_http; run_http(host='127.0.0.1', port=8000)"