"""CLI for MS Access MCP Server versioning operations."""
import os
import secrets
import typer
from pathlib import Path
from typing import Literal, Optional

from ms_access_mcp.services.backend_selector import (
    BackendCapabilities,
    BackendSelector,
    VBA_CAPS,
)

app = typer.Typer(help="MS Access versioning CLI")


BACKEND_OPT = typer.Option("odbc", "--backend", "-b", help="Adapter backend: 'odbc' (cross-platform, default) or 'com' (Windows only, for VBA/forms)")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind address"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="API key (or set ACCESS_MCP_API_KEY env var)"),
    allowed_dirs: Optional[str] = typer.Option(None, "--allowed-dirs", help="Allowed directories (semicolon-separated)"),
    transport: Literal["stdio", "http", "sse", "streamable-http"] = typer.Option("http", "--transport", "-t", help="Transport type"),
    ssl_keyfile: Optional[str] = typer.Option(None, "--ssl-keyfile", help="SSL key file for TLS"),
    ssl_certfile: Optional[str] = typer.Option(None, "--ssl-certfile", help="SSL certificate file for TLS"),
) -> None:
    """Start the MCP server with HTTP transport."""
    # Set environment variables from CLI args
    if host:
        os.environ["ACCESS_MCP_HOST"] = host
    if port:
        os.environ["ACCESS_MCP_PORT"] = str(port)
    if api_key:
        os.environ["ACCESS_MCP_API_KEY"] = api_key
    if allowed_dirs:
        os.environ["ACCESS_MCP_ALLOWED_DIRS"] = allowed_dirs

    # Auto-generate API key if none provided — so users don't need to run Python commands
    if not os.environ.get("ACCESS_MCP_API_KEY"):
        generated = secrets.token_urlsafe(32)
        os.environ["ACCESS_MCP_API_KEY"] = generated
        host_display = host or "127.0.0.1"
        port_display = port or 8000
        typer.echo(f"")
        typer.echo("=" * 60)
        typer.echo("  MS Access MCP Server — No API key provided, generated one:")
        typer.echo(f"  API Key: {generated}")
        typer.echo(f"  Login at http://{host_display}:{port_display}/login")
        typer.echo("=" * 60)
        typer.echo(f"")

    # Warn on 0.0.0.0 bind unless ACCESS_MCP_ALLOW_REMOTE is set
    if host == "0.0.0.0" and not os.environ.get("ACCESS_MCP_ALLOW_REMOTE"):
        typer.echo(
            "WARNING: Binding to 0.0.0.0 exposes the server to remote connections. "
            "Set ACCESS_MCP_ALLOW_REMOTE=1 to acknowledge this risk.",
            err=True,
        )

    if transport == "stdio":
        # stdio transport uses mcp.run() directly
        from ms_access_mcp.mcp.server import mcp
        mcp.run(transport="stdio")
    else:
        # HTTP-based transports use run_http
        from ms_access_mcp.mcp.server import run_http
        run_http(
            host=host,
            port=port,
            transport=transport,
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
        )


# Global adapter init helper — called by most commands
def _get_adapter(
    db_path: str,
    backend: Literal["odbc", "com", "auto"] = "odbc",
    capabilities: BackendCapabilities | None = None,
):
    """Create and connect an adapter via BackendSelector. backend = 'odbc' (default) or 'com'."""
    adapter = BackendSelector.get_adapter(db_path=db_path, backend=backend, capabilities=capabilities)
    if not adapter.connect(db_path):
        raise typer.Exit(code=1)
    return adapter


def _print_result(result: dict):
    """Print result summary and exit with appropriate code."""
    if result.get("success"):
        typer.echo("Success: " + result.get("message", "Done"))
        raise typer.Exit(code=0)
    else:
        typer.echo("Error: " + result.get("error", "Unknown error"))
        raise typer.Exit(code=1)


@app.command()
def export_all(
    directory: str = typer.Option(..., "--dir", help="Output directory"),
    dedup: bool = typer.Option(True, "--dedup/--no-dedup", help="Skip unchanged files"),
    module_ext: str = typer.Option(".bas", "--module-ext", help="Module file extension"),
    db_path: str = typer.Option(..., "--db", help="Path to .accdb file"),
    backend: Literal["odbc", "com", "auto"] = BACKEND_OPT,
):
    """Export all objects to text files for version control."""
    from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
    adapter = _get_adapter(db_path, backend)
    orch = VersioningOrchestrator()
    result = orch.export_all(directory, adapter, dedup=dedup, module_ext=module_ext)
    adapter.disconnect()
    _print_result(result)


@app.command()
def compare_versioning(
    directory: str = typer.Option(..., "--dir", help="Export directory"),
    db_path: str = typer.Option(..., "--db", help="Path to .accdb file"),
    backend: Literal["odbc", "com", "auto"] = BACKEND_OPT,
):
    """Compare database state against export directory."""
    from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
    adapter = _get_adapter(db_path, backend)
    orch = VersioningOrchestrator()
    result = orch.compare(directory, adapter)
    adapter.disconnect()
    if result.get("success"):
        new = result.get("new", [])
        missing = result.get("missing", [])
        changed = result.get("changed", [])
        unchanged = result.get("unchanged", [])
        typer.echo(f"New: {len(new)}, Missing: {len(missing)}, Changed: {len(changed)}, Unchanged: {len(unchanged)}")
        if new:
            typer.echo(f"  New objects: {[o['name'] for o in new]}")
        if missing:
            typer.echo(f"  Missing: {[o['name'] for o in missing]}")
        if changed:
            typer.echo(f"  Changed: {[o['name'] for o in changed]}")
        if new or missing or changed:
            raise typer.Exit(code=1)
        raise typer.Exit(code=0)
    else:
        typer.echo("Error: " + result.get("error", "Unknown error"))
        raise typer.Exit(code=1)


@app.command(name="git-hook-init")
def git_hook_init(
    repo_path: str = typer.Option(".", "--repo", help="Repository root path"),
):
    """Install a pre-commit hook that auto-exports before each commit."""
    from ms_access_mcp.orchestrators.versioning import VersioningOrchestrator
    orch = VersioningOrchestrator()
    result = orch.install_git_hook(repo_path)
    _print_result(result)


@app.command()
def export_vba(
    module_name: str,
    db_path: str = typer.Option(..., "--db", help="Path to .accdb file"),
    output: Optional[Path] = None,
    backend: Literal["odbc", "com", "auto"] = BACKEND_OPT,
):
    """Export a VBA module to a .bas file. Requires --backend com (Windows only)."""
    output_path = output or Path(f"{module_name}.bas")
    typer.echo(f"Exporting module '{module_name}' to {output_path}")
    adapter = _get_adapter(db_path, backend, capabilities=VBA_CAPS)
    code = adapter.export_module_to_text(module_name)
    output_path.write_text(code or "", encoding="utf-8")
    adapter.disconnect()
    typer.echo(f"Exported to {output_path}")


def main():
    app()


if __name__ == "__main__":
    main()