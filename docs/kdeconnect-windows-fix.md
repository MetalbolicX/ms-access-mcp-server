# KDE Connect Stopped Working on Windows

## Symptoms

KDE Connect was working fine and suddenly stopped detecting devices on
the local network. The app opens, processes are running, but it neither
discovers nor connects to previously paired devices.

## Root Cause

Windows Update typically causes two issues at the same time:

1.  **Network switches to Public profile** — Windows blocks device
    discovery on public networks. KDE Connect relies on UDP multicast
    for discovery.

2.  **Firewall rules get wiped** — Windows Update resets third-party
    firewall rules. Without explicit rules for ports 1714–1764 (TCP and
    UDP), the firewall blocks all communication.

Both changes are silent: no notification, the app looks normal, but
there is no connectivity.

## Solution

### Prerequisite

The firewall and network profile commands require **PowerShell as
Administrator**.

1.  Open PowerShell as Administrator (Win+X → "Terminal (Admin)" or
    "Windows PowerShell (Admin)").

2.  Run these commands in order:

```powershell
# 1. Check the actual network interface name
Get-NetConnectionProfile

# The SSID appears under "Name" and the interface alias under
# "InterfaceAlias". Use that alias in the next command.

# 2. Switch the network to Private
Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private

# 3. Create firewall rules for KDE Connect
New-NetFirewallRule -DisplayName "KDE Connect (TCP)" -Direction Inbound -Protocol TCP -LocalPort 1714-1764 -Action Allow
New-NetFirewallRule -DisplayName "KDE Connect (UDP)" -Direction Inbound -Protocol UDP -LocalPort 1714-1764 -Action Allow
```

3.  **Restart KDE Connect**: kill the `kdeconnect-app` and
    `kdeconnect-indicator` processes from Task Manager, then reopen the
    app.

### Verification

```powershell
# Check the network is now Private
Get-NetConnectionProfile | Select-Object Name, NetworkCategory

# Check firewall rules exist
Get-NetFirewallRule -DisplayName "KDE Connect*" | Format-Table DisplayName, Direction, Action, Enabled
```

## Prevention

After the next Windows Update, if KDE Connect breaks again:

1.  Check `Get-NetConnectionProfile` to see if the network reverted to
    `Public`.
2.  Check `Get-NetFirewallRule -DisplayName "KDE Connect*"` to see if
    the rules are still there.

Usually only the firewall rules are lost, so re-running the
`New-NetFirewallRule` commands is enough.
