# Deployment Guide

## Windows Server Setup

### 1. Install

```cmd
uv sync --extra windows
```

### 2. Generate API key

```cmd
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Configure environment

```cmd
set ACCESS_MCP_API_KEY=<your-generated-key>
set ACCESS_MCP_ALLOWED_DIRS=C:\MyDatabases;D:\SharedDBs
```

### 4. Start server

Using the installed script command:

```cmd
ms-access-mcp serve
```

Or using Python module syntax:

```cmd
python -m ms_access_mcp.cli.main serve
```

With CLI args:

```cmd
ms-access-mcp serve --host 127.0.0.1 --port 8000 --api-key <key> --allowed-dirs "C:\Data;D:\DBs"
```

With TLS certificates:

```cmd
ms-access-mcp serve --ssl-keyfile /path/to/key.pem --ssl-certfile /path/to/cert.pem
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

## Linux Server Setup (data-only)

On Linux, the server runs with ODBC only. COM-dependent operations
(VBA editing, forms, reports, macros, compact/repair) are unavailable.

### 1. Install system dependencies

```bash
sudo apt install unixodbc mdbtools mdbtools-odbc
```

### 2. Register the ODBC driver

```bash
# /etc/odbcinst.ini
cat <<'EOF' | sudo tee -a /etc/odbcinst.ini
[MDBTools]
Description = MDB Tools ODBC driver
Driver      = /usr/lib/x86_64-linux-gnu/odbc/libmdbodbc.so
Setup       = /usr/lib/x86_64-linux-gnu/odbc/libmdbodbcS.so
EOF
```

OdbcAdapter tries Windows driver names first. Create a matching alias:

```bash
cat <<'EOF' | sudo tee /etc/odbc.ini
[Microsoft Access Driver (*.mdb, *.accdb)]
Description = MDB Tools driver
Driver      = /usr/lib/x86_64-linux-gnu/odbc/libmdbodbc.so
Setup       = /usr/lib/x86_64-linux-gnu/odbc/libmdbodbcS.so
EOF
```

### 3. Install Python dependencies

```bash
uv sync   # pywin32 not needed on Linux
```

### 4. Configure and start

```bash
export ACCESS_MCP_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export ACCESS_MCP_ALLOWED_DIRS=/path/to/databases

ms-access-mcp serve
```

### Limitations on Linux

- No VBA operations (`get_vba_code`, `set_vba_code`, `compile_vba`)
- No form/report UI automation (`open_form`, `close_form`, etc.)
- No compact/repair (`compact_repair`)
- No linked table management (`create_linked_table`, etc.)
- `get_relationships` returns empty (ODBC cannot expose Access relationship metadata)

Use `--backend com` on Windows to access COM-dependent operations.

## Security

### Firewall

Only expose port 8000 to trusted networks:

```cmd
netsh advfirewall firewall add rule name="MCP Access Server" dir=in action=allow protocol=tcp localport=8000 remoteip=192.168.1.0/24
```

### TLS

You can enable TLS directly via CLI options:

```cmd
ms-access-mcp serve --ssl-keyfile /path/to/key.pem --ssl-certfile /path/to/cert.pem
```

Alternatively, use a reverse proxy (nginx/caddy) with TLS termination:

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

### Remote Binding Warning

Binding to `0.0.0.0` exposes the server to remote connections. The server will warn when starting with `--host 0.0.0.0` unless `ACCESS_MCP_ALLOW_REMOTE=1` is set.

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
ms-access-mcp serve
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ACCESS_MCP_API_KEY` | Yes | — | Bearer token for HTTP auth |
| `ACCESS_MCP_HOST` | No | `127.0.0.1` | Bind address |
| `ACCESS_MCP_PORT` | No | `8000` | Bind port |
| `ACCESS_MCP_ALLOWED_DIRS` | No | User home | Semicolon-separated directory whitelist |
| `ACCESS_MCP_ALLOW_REMOTE` | No | — | Set to `1` to acknowledge remote binding risk when using `0.0.0.0` |
