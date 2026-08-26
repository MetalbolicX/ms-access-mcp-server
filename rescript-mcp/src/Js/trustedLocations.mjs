// trustedLocations.mts — Typed ESM bridge for TrustedLocations.res child_process blocks
// Mirrors: src/ms_access_mcp/adapters/trusted_locations.py (Python winreg → PowerShell)
// Replaces %raw spawn block with static node:child_process ESM import.
// Security: shell:false disables shell interpretation; args are passed as-is (no shell expansion).
//          Caller (PowerShell -Command) is responsible for correct argument quoting.
import { spawn } from "node:child_process";
/** Run a PowerShell script via child_process.spawn, return trimmed stdout.
 *  Non-fatal: returns empty string on any error (process error, timeout, etc.).
 *  Matches original %raw contract exactly:
 *    - command: "powershell"
 *    - args: ["-NoProfile", "-NonInteractive", "-Command", <script>]
 *    - shell: false  (no shell expansion)
 *    - windowsHide: true
 *    - stdout collected until 'close' event
 *    - empty string on error
 */
export const runPowerShell = (cmd, args) => {
    return new Promise((resolve) => {
        let out = "";
        let settled = false;
        const opts = {
            shell: false,
            windowsHide: true,
        };
        const child = spawn(cmd, args, opts);
        child.stdout?.on("data", (d) => {
            out += d.toString();
        });
        child.on("close", () => {
            if (!settled) {
                settled = true;
                resolve(out.trim());
            }
        });
        child.on("error", () => {
            if (!settled) {
                settled = true;
                resolve("");
            }
        });
    });
};
