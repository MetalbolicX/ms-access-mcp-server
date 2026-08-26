// TrustedLocations.resi — Trusted Locations capture/restore via Windows registry
// Mirrors src/ms_access_mcp/adapters/trusted_locations.py (Python winreg → PowerShell)
// Non-fatal: failures return false/empty without throwing.

type trustedLocation = ComInterfaces.trustedLocation

// Capture current Trusted Locations from HKLM and HKCU registry.
// Returns Ok(array<trustedLocation>) or Error on failure.
// On non-Windows returns Ok([]) without error.
let capture: unit => Promise.t<result<array<trustedLocation>, Errors.t>>

// Restore Trusted Locations to registry.
// Returns Ok(true) on success, Ok(false) on partial failure, Error on fatal.
// Writes HKLM and HKCU keys using LocationN naming (Location1, Location2, ...).
let restore: array<trustedLocation> => Promise.t<result<bool, Errors.t>>

// Platform check — true only on Windows
let isWindows: unit => bool
