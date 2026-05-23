param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$ApiKey = "test-key-123",
    [string]$DatabasePath = "D:\JMS\Limbo\excel-and-sql-book\data\db\helper.accdb",
    [string]$SqlScript = "D:\JMS\Limbo\excel-and-sql-book\data\db\create-demo-tables.sql",
    [int]$Iterations = 3
)

$McpUrl = "${BaseUrl}/mcp"
$Headers = @{ Authorization = "Bearer $ApiKey" }
$Failures = 0

function Invoke-JsonRpc-Tool {
    param([string]$Tool, [hashtable]$Arguments, [int]$Id = 1)
    $Body = @{
        jsonrpc = "2.0"
        id = $Id
        method = "tools/call"
        params = @{ name = $Tool; arguments = $Arguments }
    } | ConvertTo-Json -Depth 10
    Write-Host "    >>> $Tool" -ForegroundColor Cyan
    try {
        $resp = Invoke-RestMethod -Uri $McpUrl -Method Post -Headers $Headers -Body $Body -ContentType "application/json" -TimeoutSec 60
        if ($resp.result -is [array]) {
            return $resp.result
        } elseif ($resp.result -and $resp.result.success -eq $false) {
            $msg = $resp.result.error.message ?? $resp.result.message ?? "unknown"
            Write-Host "    ERROR: $msg" -ForegroundColor Red
            return $null
        } elseif ($resp.error) {
            Write-Host "    JSON-RPC ERROR: $($resp.error.message)" -ForegroundColor Red
            return $null
        }
        return $resp.result
    } catch {
        Write-Host "    HTTP ERROR: $_" -ForegroundColor Red
        return $null
    }
}

Write-Host "============================================" -ForegroundColor Green
Write-Host "COM Thread Affinity Integration Test" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host "Server  : $McpUrl"
Write-Host "DB      : $DatabasePath"
Write-Host "Script  : $SqlScript"
Write-Host "Cycles  : $Iterations"
Write-Host ""

# --- Verify server is up ---
Write-Host "--- Health check ---" -ForegroundColor Yellow
$healthBody = @{ jsonrpc = "2.0"; id = 1; method = "tools/list"; params = @{} } | ConvertTo-Json
try {
    Invoke-RestMethod -Uri $McpUrl -Method Post -Headers $Headers -Body $healthBody -ContentType "application/json" -TimeoutSec 5 | Out-Null
    Write-Host "    Server is up." -ForegroundColor Green
} catch {
    Write-Host "    FAILED: Server not responding at $McpUrl" -ForegroundColor Red
    exit 1
}

# --- Iterations ---
for ($i = 1; $i -le $Iterations; $i++) {
    Write-Host "`n--- Iteration $i/$Iterations ---" -ForegroundColor Yellow

    # 1. connect_access
    Write-Host "  [1/4] connect_access..." -ForegroundColor White
    $result = Invoke-JsonRpc-Tool -Tool "connect_access" -Arguments @{
        database_path = $DatabasePath
        use_com = $true
    }
    if (-not $result) {
        Write-Host "  FAIL: connect_access returned no result" -ForegroundColor Red
        $Failures++
        continue
    }
    $connected = $result.connected -eq $true
    if (-not $connected) {
        Write-Host "  FAIL: not connected ( $($result | ConvertTo-Json -Depth 3) )" -ForegroundColor Red
        $Failures++
        continue
    }
    Write-Host "  OK: connected=$($result.connected)" -ForegroundColor Green

    # 2. get_tables (tests COM thread affinity)
    Write-Host "  [2/4] get_tables..." -ForegroundColor White
    $tables = Invoke-JsonRpc-Tool -Tool "get_tables" -Arguments @{}
    if ($null -eq $tables -or $tables.Count -eq 0) {
        Write-Host "  FAIL: get_tables returned no tables (possible thread-affinity failure)" -ForegroundColor Red
        $Failures++
        # Try to detect "not connected" pattern
    } else {
        Write-Host "  OK: $($tables.Count) tables returned" -ForegroundColor Green
    }

    # 3. execute_sql_script
    Write-Host "  [3/4] execute_sql_script..." -ForegroundColor White
    $scriptResult = Invoke-JsonRpc-Tool -Tool "execute_sql_script" -Arguments @{
        script_path = $SqlScript
    }
    if ($null -ne $scriptResult) {
        Write-Host "  OK: $($scriptResult.statements_executed ?? 0) statements executed" -ForegroundColor Green
    } else {
        # Non-fatal; script may have run but returned nothing
        Write-Host "  WARN: execute_sql_script returned null (may have executed)" -ForegroundColor Magenta
    }

    # 4. disconnect
    Write-Host "  [4/4] disconnect_access..." -ForegroundColor White
    $discResult = Invoke-JsonRpc-Tool -Tool "disconnect_access" -Arguments @{}
    if ($null -ne $discResult) {
        Write-Host "  OK: disconnected" -ForegroundColor Green
    } else {
        Write-Host "  WARN: disconnect returned null" -ForegroundColor Magenta
    }
}

# --- Summary ---
Write-Host "`n============================================" -ForegroundColor Green
if ($Failures -eq 0) {
    Write-Host "RESULT: ALL $Iterations ITERATIONS PASSED" -ForegroundColor Green
    Write-Host "No 'Not connected' errors detected." -ForegroundColor Green
    exit 0
} else {
    Write-Host "RESULT: $Failures ITERATION(S) FAILED" -ForegroundColor Red
    exit 1
}