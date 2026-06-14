# Additional Power/ACPI diagnostics
Write-Host "=== POWER CONFIGURATION ===" -ForegroundColor Cyan
powercfg /batteryreport /output "$env:TEMP\battery_report.html" 2>$null
$battery = Get-WmiObject Win32_Battery -ErrorAction SilentlyContinue
if ($battery) {
    $battery | Format-List Status, BatteryStatus, EstimatedChargeRemaining, DesignCapacity, FullChargeCapacity
} else {
    Write-Host "No battery detected (desktop or AC-only)" -ForegroundColor Yellow
}

Write-Host "`n=== POWER SCHEME ===" -ForegroundColor Cyan
powercfg /list | Select-String "Active*"

Write-Host "`n=== S3 SLEEP STATE CHECK ===" -ForegroundColor Cyan
$acpi = Get-WmiObject -Class Win32_ACPIEnabledAvailable -ErrorAction SilentlyContinue
if ($acpi) {
    $acpi | Format-List *
} else {
    Write-Host "Checking via registry..." -ForegroundColor Yellow
    $sleep = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Power" -ErrorAction SilentlyContinue
    if ($sleep) {
        $sleep | Format-List *
    }
}

Write-Host "`n=== RECENT CRITICAL ERRORS ===" -ForegroundColor Cyan
Get-EventLog -LogName System -Newest 100 | Where-Object { $_.EntryType -eq 'Critical' } | Select-Object TimeGenerated, Source, Message | Format-Table -AutoSize -Wrap

Write-Host "`n=== KERNEL POWER ERRORS ===" -ForegroundColor Cyan
Get-EventLog -LogName System -Newest 50 | Where-Object { $_.Source -match "Kernel-Power|Power-Troubleshooter|Hyper-V" } | Select-Object TimeGenerated, EntryType, Source, Message | Format-Table -AutoSize -Wrap

Write-Host "`n=== CHECK IF USB DEVICE IS CAUSING ISSUES ===" -ForegroundColor Cyan
Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.Status -ne 'OK' } | Select-Object FriendlyName, Status, Problem, ProblemDescription | Format-Table -AutoSize

Write-Host "`n=== EVENT 1001 BUGCHECKS ===" -ForegroundColor Cyan
Get-WinEvent -FilterHashtable @{LogName='System';Id=1001} -MaxEvents 10 -ErrorAction SilentlyContinue | Select-Object TimeCreated, @{N='BugCheck';E={$_.Properties[0].Value}}, @{N='DumpFile';E={$_.Properties[1].Value}} | Format-Table -AutoSize
