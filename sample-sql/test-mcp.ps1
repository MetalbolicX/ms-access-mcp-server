param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$ApiKey = "test-key-123",
    [string]$DatabasePath = "D:\JMS\Limbo\excel-and-sql-book\data\db\helper.accdb",
    [string]$SqlScript = "D:\JMS\Limbo\excel-and-sql-book\data\db\create-demo-tables.sql"
)

$McpUrl = "${BaseUrl}/mcp"
$Headers = @{ Authorization = "Bearer $ApiKey" }

function Invoke-JsonRpc-Tool {
    param([string]$Tool, [hashtable]$Arguments, [int]$Id = 1)
    $Body = @{
        jsonrpc = "2.0"
        id = $Id
        method = "tools/call"
        params = @{ name = $Tool; arguments = $Arguments }
    } | ConvertTo-Json -Depth 10
    Write-Host "`n>>> $Tool" -ForegroundColor Cyan
    try {
        $resp = Invoke-RestMethod -Uri $McpUrl -Method Post -Headers $Headers -Body $Body -ContentType "application/json"
        if ($resp.result) {
            return $resp.result
        } elseif ($resp.error) {
            Write-Host "ERROR: $($resp.error.message)" -ForegroundColor Red
            return $null
        }
        return $resp
    } catch {
        Write-Host "HTTP ERROR: $_" -ForegroundColor Red
        return $null
    }
}

Write-Host "============================================" -ForegroundColor Green
Write-Host "MS Access MCP Server - PowerShell Test Suite" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host "Server : $McpUrl"
Write-Host "DB     : $DatabasePath"
Write-Host "Script : $SqlScript"
Write-Host ""

# --- Step 1: tools/list ---
Write-Host "--- Step 1: List available tools ---" -ForegroundColor Yellow
$listBody = @{ jsonrpc = "2.0"; id = 1; method = "tools/list"; params = @{} } | ConvertTo-Json
try {
    $tools = Invoke-RestMethod -Uri $McpUrl -Method Post -Headers $Headers -Body $listBody -ContentType "application/json"
    Write-Host ($tools | ConvertTo-Json -Depth 5) -ForegroundColor White
} catch {
    Write-Host "FAILED: $_" -ForegroundColor Red
    exit 1
}

# --- Step 2: connect_access ---
Write-Host "`n--- Step 2: Connect to Access database ---" -ForegroundColor Yellow
$result = Invoke-JsonRpc-Tool -Tool "connect_access" -Arguments @{
    database_path = $DatabasePath
    use_com = $true
}
if ($result) {
    Write-Host ($result | ConvertTo-Json -Depth 5) -ForegroundColor White
} else { Write-Host "SKIPPING remaining steps due to error." -ForegroundColor Red; exit 1 }

# --- Step 3: execute_sql_script ---
Write-Host "`n--- Step 3: Execute SQL script ---" -ForegroundColor Yellow
$result = Invoke-JsonRpc-Tool -Tool "execute_sql_script" -Arguments @{
    script_path = $SqlScript
}
if ($result) { Write-Host ($result | ConvertTo-Json -Depth 5) -ForegroundColor White }
else { Write-Host "WARNING: execute_sql_script returned no result (may still have executed)" -ForegroundColor Magenta }

# --- Step 4: get_tables ---
Write-Host "`n--- Step 4: Get tables ---" -ForegroundColor Yellow
$result = Invoke-JsonRpc-Tool -Tool "get_tables" -Arguments @{}
if ($result) { Write-Host ($result | ConvertTo-Json -Depth 5) -ForegroundColor White }
else { Write-Host "FAILED: get_tables returned no result." -ForegroundColor Red }

# --- Step 5: disconnect ---
Write-Host "`n--- Step 5: Disconnect ---" -ForegroundColor Yellow
$result = Invoke-JsonRpc-Tool -Tool "disconnect_access" -Arguments @{}
if ($result) { Write-Host ($result | ConvertTo-Json -Depth 5) -ForegroundColor White }
else { Write-Host "WARNING: disconnect returned no result (may have succeeded anyway)" -ForegroundColor Magenta }

Write-Host "`n============================================" -ForegroundColor Green
Write-Host "Test suite complete." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
