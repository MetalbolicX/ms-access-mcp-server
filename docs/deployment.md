# Deployment Guide

## Windows Server Setup

### 1. Install

```cmd
pip install -e ".[windows]"
```

### 2. Generate API key

```cmd
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Configure environment

```cmd
set ACCESS_MCP_API_KEY=<your-generated-key>
set ACCESS_MCP_ALLOWED_DIRS=C:\MyDatabases;D:\SharedDBs
set ACCESS_MCP_HOST=127.0.0.1
set ACCESS_MCP_PORT=8000
```

### 4. Start server

```cmd
python -m ms_access_mcp.cli.main serve
```

Or with CLI args:

```cmd
python -m ms_access_mcp.cli.main serve --host 0.0.0.0 --port 8000 --api-key <key> --allowed-dirs "C:\Data;D:\DBs"
```

## Client Setup (Linux/WSL)

### opencode.json

```json
{
  "mcpServers": {
    "ms-access": {
      "transport": "http",
      "url": "http://<windows-ip>:8000/mcp",
      "headers": {
        "Authorization": "Bearer <your-api-key>"
      }
    }
  }
}
```

## Security

### Firewall

Only expose port 8000 to trusted networks:

```cmd
netsh advfirewall firewall add rule name="MCP Access Server" dir=in action=allow protocol=tcp localport=8000 remoteip=192.168.1.0/24
```

### TLS (recommended for production)

Use a reverse proxy (nginx/caddy) with TLS termination:

```
[Client] --HTTPS--> [Reverse Proxy:443] --HTTP--> [MCP Server:8000]
```

Example nginx config:

```nginx
server {
    listen 443 ssl;
    server_name ms-access.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /mcp {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        # Pass Authorization header to MCP server
        proxy_set_header Authorization $http_authorization;
    }
}
```

### Database path restrictions

The server only allows access to `.accdb` files in configured directories.
Path traversal attacks (`../../etc/passwd.accdb`) are blocked.
UNC paths (`\\server\share\db.accdb`) are blocked.

## Quick Start

```cmd
# 1. Generate a secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Set the key (add to your shell profile for persistence)
set ACCESS_MCP_API_KEY=<generated-key>

# 3. Set allowed directories
set ACCESS_MCP_ALLOWED_DIRS=C:\AccessDatabases

# 4. Start the server
python -m ms_access_mcp.cli.main serve --host 127.0.0.1 --port 8000
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ACCESS_MCP_API_KEY` | Yes | — | Bearer token for HTTP auth |
| `ACCESS_MCP_HOST` | No | `127.0.0.1` | Bind address |
| `ACCESS_MCP_PORT` | No | `8000` | Bind port |
| `ACCESS_MCP_ALLOWED_DIRS` | No | User home | Semicolon-separated directory whitelist |