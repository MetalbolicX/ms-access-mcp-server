# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in MS Access MCP Server, please report it responsibly.

### How to Report

1. **Do NOT** open a public GitHub issue for security vulnerabilities.
2. Email the maintainers directly with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours.
- **Initial Assessment**: We will assess the severity and impact of the vulnerability.
- **Fix Timeline**: We will work to provide a fix based on severity:
  - Critical: Fix within 7 days, coordinate disclosure
  - High: Fix within 30 days
  - Medium: Fix within 90 days
  - Low: Fix in next release cycle

### Security Best Practices for Users

- **API Keys**: Use `ACCESS_MCP_API_KEY` of at least 32 characters with high entropy. Generate with:
  ```
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- **Network Exposure**: Default bind is `127.0.0.1` (localhost only). Do not expose to untrusted networks without TLS.
- **Allowed Directories**: Use `ACCESS_MCP_ALLOWED_DIRS` to restrict file system access to trusted directories only.

### Known Security Measures

- API key comparison uses `hmac.compare_digest` to prevent timing side-channel attacks.
- All file access passes through `PathGuard` validation.
- Destructive tools require explicit `confirm=True` parameter.
- Process cleanup (`taskkill`) is scoped to owned PIDs only, not global.