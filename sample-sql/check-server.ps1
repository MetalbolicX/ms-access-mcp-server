$ErrorActionPreference = "Stop"
$headers = @{ Authorization = "Bearer test-key-123"; Accept = "application/json, text/event-stream" }
$baseUrl = "http://127.0.0.1:8000/mcp"

Write-Host "=== INIT ==="
$body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0"}}}'
try {
    $webResp = Invoke-WebRequest -Uri $baseUrl -Method Post -Headers $headers -Body $body -ContentType "application/json" -TimeoutSec 10
    Write-Host "INIT OK (status $($webResp.StatusCode))"
    Write-Host "Headers:"
    $webResp.Headers.Keys | ForEach-Object { Write-Host "  $_ : $($webResp.Headers[$_])" }
    Write-Host "--- Content ---"
    Write-Host ($webResp.Content | ConvertFrom-Json | ConvertTo-Json -Depth 4)
} catch {
    Write-Host "INIT FAILED: $($_.Exception.Message)"
    exit 1
}
