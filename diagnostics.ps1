# Get recent critical system events
Write-Host "=== Critical System Events (Event ID 41, 1001, 6008, 7036) ===" -ForegroundColor Cyan
Get-WinEvent -LogName System -MaxEvents 200 | Where-Object {
    $_.Id -eq 41 -or $_.Id -eq 1001 -or $_.Id -eq 6008 -or $_.Id -eq 7036
} | Select-Object TimeCreated, Id, LevelDisplayName, Message | Format-List

Write-Host "`n=== Recent Errors (Level 2) ===" -ForegroundColor Cyan
Get-WinEvent -LogName System -MaxEvents 100 | Where-Object {
    $_.Level -eq 2
} | Select-Object TimeCreated, Id, ProviderName, Message | Format-List

Write-Host "`n=== Application Crashes ===" -ForegroundColor Cyan
Get-WinEvent -LogName Application -MaxEvents 50 | Where-Object {
    $_.Level -eq 2
} | Select-Object TimeCreated, Id, ProviderName, Message | Format-List