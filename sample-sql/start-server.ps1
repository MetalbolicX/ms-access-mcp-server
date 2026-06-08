# MS Access MCP Server - Sample SQL Directory Startup Script
#
# Environment variables can be set here or in a .env file at the project root.
# .env is already in .gitignore — safe for secrets.
#
# Required environment variable:
#   ACCESS_MCP_API_KEY  — Must be >= 32 characters with high entropy
#   Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
#
# Optional:
#   ACCESS_MCP_ALLOWED_DIRS — Semicolon-separated directory whitelist
#   ACCESS_MCP_HOST — Bind address (default: 127.0.0.1)
#   ACCESS_MCP_PORT — Bind port (default: 8000)

# Prompt for API key if not set
if (-not $env:ACCESS_MCP_API_KEY) {
    Write-Host "ACCESS_MCP_API_KEY is not set. Please enter a secure API key (>= 32 chars):" -ForegroundColor Yellow
    $key = Read-Host -AsSecureString
    $env:ACCESS_MCP_API_KEY = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($key))
}

# Set allowed directories to user home if not specified
if (-not $env:ACCESS_MCP_ALLOWED_DIRS) {
    $env:ACCESS_MCP_ALLOWED_DIRS = $env:USERPROFILE
}

python -c "from ms_access_mcp.mcp.server import run_http; run_http(host='127.0.0.1', port=8000)"