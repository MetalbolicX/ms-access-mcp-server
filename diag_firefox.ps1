# Firefox Diagnostic Script
Write-Host "=== SYSTEM INFO ===" -ForegroundColor Cyan
Get-WmiObject Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, TotalVisibleMemorySize, FreePhysicalMemory | Format-List

Write-Host "`n=== FIREFOX PROCESSES ===" -ForegroundColor Cyan
Get-Process firefox -ErrorAction SilentlyContinue | Select-Object Name, Id, CPU, WorkingSet64, StartTime, Responding | Format-Table -AutoSize

Write-Host "`n=== DISK STATUS ===" -ForegroundColor Cyan
Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3" | Select-Object DeviceID, @{N="Size(GB)";E={[math]::Round($_.Size/1GB,2)}}, @{N="Free(GB)";E={[math]::Round($_.FreeSpace/1GB,2)}}, @{N="Free%";E={[math]::Round($_.FreeSpace/$_.Size*100,1)}} | Format-Table -AutoSize

Write-Host "`n=== SMART STATUS ===" -ForegroundColor Cyan
Get-WmiObject -Class Win32_DiskDrive | Select-Object Model, Status, MediaType | Format-Table -AutoSize

Write-Host "`n=== RECENT SYSTEM ERRORS (Last 24h) ===" -ForegroundColor Cyan
$cutoff = (Get-Date).AddDays(-1)
Get-EventLog -LogName System -Newest 50 | Where-Object { $_.TimeGenerated -gt $cutoff -and $_.EntryType -in @('Error','Critical') } | Select-Object TimeGenerated, EntryType, Source, Message | Format-Table -AutoSize -Wrap

Write-Host "`n=== RECENT APPLICATION ERRORS (Last 24h) ===" -ForegroundColor Cyan
Get-EventLog -LogName Application -Newest 30 | Where-Object { $_.TimeGenerated -gt $cutoff -and $_.EntryType -in @('Error','Critical') } | Select-Object TimeGenerated, EntryType, Source, Message | Format-Table -AutoSize -Wrap

Write-Host "`n=== FIREFOX PROFILE LOCATION ===" -ForegroundColor Cyan
$firefoxPath = "$env:APPDATA\Mozilla\Firefox\Profiles"
if (Test-Path $firefoxPath) {
    Get-ChildItem $firefoxPath -Directory | Select-Object Name, LastWriteTime | Format-Table -AutoSize
} else {
    Write-Host "Firefox profile path not found" -ForegroundColor Yellow
}

Write-Host "`n=== GPU INFO ===" -ForegroundColor Cyan
Get-WmiObject Win32_VideoController | Select-Object Name, DriverVersion, Status | Format-Table -AutoSize

Write-Host "`n=== RECENTLY MODIFIED FILES IN FIREFOX PROFILE ===" -ForegroundColor Cyan
if (Test-Path $firefoxPath) {
    Get-ChildItem $firefoxPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-24) } | Select-Object Name, LastWriteTime, Length | Sort-Object LastWriteTime -Descending | Select-Object -First 10 | Format-Table -AutoSize
}
