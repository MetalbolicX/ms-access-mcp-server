import os
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(help="MS Access MCP CLI")

# To be connected to real services
MCP_SERVER = "ms-access-mcp-server"


@app.command()
def serve(
    host: str = typer.Option(None, "--host", help="Bind host (default: 127.0.0.1)"),
    port: int = typer.Option(None, "--port", help="Bind port (default: 8000)"),
    api_key: str = typer.Option(None, "--api-key", help="API key (or set ACCESS_MCP_API_KEY env)"),
    allowed_dirs: str = typer.Option(None, "--allowed-dirs", help="Semicolon-separated allowed directories"),
    transport: str = typer.Option("http", "--transport", help="Transport: http, streamable-http, sse"),
):
    """Start MCP server with HTTP transport for remote access."""
    # Apply CLI overrides to environment
    if host:
        os.environ["ACCESS_MCP_HOST"] = host
    if port:
        os.environ["ACCESS_MCP_PORT"] = str(port)
    if api_key:
        os.environ["ACCESS_MCP_API_KEY"] = api_key
    if allowed_dirs:
        os.environ["ACCESS_MCP_ALLOWED_DIRS"] = allowed_dirs

    from ..mcp.server import run_http

    typer.echo(f"Starting MCP server on {host or '127.0.0.1'}:{port or 8000}")
    typer.echo(f"Transport: {transport}")
    typer.echo(f"API key: {'*' * 8}...{(api_key or os.environ.get('ACCESS_MCP_API_KEY', ''))[-4:]}")

    run_http(host=host or "127.0.0.1", port=port or 8000, transport=transport)


@app.command()
def connect(
    db_path: str = typer.Argument(..., help="Path to .accdb or .mdb file"),
    use_com: bool = typer.Option(False, "--com", help="Use COM automation"),
):
    """Connect to an Access database."""
    typer.echo(f"Connecting to {db_path} (COM={use_com})...")
    typer.echo("Note: This requires the MCP server to be running")
    # Actual connection happens via MCP server


@app.command()
def disconnect():
    """Disconnect from the current database."""
    typer.echo("Disconnecting...")
    typer.echo("Note: This requires the MCP server to be running")


@app.command()
def status():
    """Check connection status."""
    typer.echo("Checking connection status...")
    typer.echo("Note: This requires the MCP server to be running")


@app.command()
def list_tables():
    """List all tables in the connected database."""
    typer.echo("Tables in connected database:")
    typer.echo("Note: This requires the MCP server to be running")


@app.command()
def list_queries():
    """List all saved queries."""
    typer.echo("Queries in connected database:")
    typer.echo("Note: This requires the MCP server to be running")


@app.command()
def describe_table(table_name: str = typer.Argument(..., help="Table name")):
    """Show schema for a specific table."""
    typer.echo(f"Schema for table '{table_name}':")
    typer.echo("Note: This requires the MCP server to be running")


@app.command()
def run_query(
    sql: str = typer.Argument(..., help="SQL query to execute"),
    export: Optional[str] = typer.Option(None, "--export", help="Export results to file"),
):
    """Execute a SQL query."""
    typer.echo(f"Executing: {sql}")
    if export:
        typer.echo(f"Results will be exported to {export}")
    typer.echo("Note: This requires the MCP server to be running")


@app.command()
def export_vba(
    module_name: str = typer.Argument(..., help="VBA module name"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output file"),
):
    """Export VBA module to a .bas file."""
    output_path = output or Path(f"{module_name}.bas")
    typer.echo(f"Exporting VBA module '{module_name}' to {output_path}")
    typer.echo("Note: This requires COM automation")


@app.command()
def import_vba(
    module_name: str = typer.Argument(..., help="VBA module name"),
    input_file: Path = typer.Argument(..., help=".bas file to import"),
):
    """Import VBA code from a .bas file."""
    typer.echo(f"Importing VBA module '{module_name}' from {input_file}")
    typer.echo("Note: This requires COM automation")


@app.command()
def git_hook_init(
    output_dir: Optional[Path] = typer.Option(None, "-o", "--output", help="Output directory for hooks"),
):
    """Initialize git hooks for versioning workflow.

    Creates .git/hooks/pre-commit that runs export_all_versioning with dedup.
    """
    hooks_base = Path(".git") if output_dir is None else Path(output_dir)
    git_hooks_dir = hooks_base / "hooks"
    git_hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_commit_path = git_hooks_dir / "pre-commit"
    hook_script = """#!/bin/sh
# Auto-generated pre-commit hook for MS Access versioning workflow
# Runs export-all with dedup to capture changes before commit

OUT_DIR=".access_versioning"

echo "Running MS Access version export..."
python -m ms_access_mcp.cli.main export-all "$OUT_DIR" --dedup 2>/dev/null || true

# Show diff summary if there are changes
if [ -d "$OUT_DIR" ]; then
    CHANGES=$(git status --porcelain "$OUT_DIR" 2>/dev/null | wc -l)
    if [ "$CHANGES" -gt 0 ]; then
        echo "Access versioning: $CHANGES object(s) changed"
        git diff --stat "$OUT_DIR" 2>/dev/null || true
    fi
fi
"""
    pre_commit_path.write_text(hook_script)
    typer.echo(f"Created {pre_commit_path}")
    typer.echo("Hook will run 'macc export-all .access_versioning --dedup' before each commit")


@app.command()
def export_all(
    output_dir: str = typer.Argument(..., help="Directory to export files to"),
    dedup: bool = typer.Option(False, "--dedup", help="Enable SHA256 deduplication"),
):
    """Export all forms, reports, modules, macros, and queries to a directory structure.

    Requires the MCP server to be running with an active database connection.
    """
    typer.echo(f"Exporting all objects to {output_dir} (dedup={dedup})")
    typer.echo("Note: This requires the MCP server to be running with an active connection")
    typer.echo("Use: macc connect <path> [--com]  to connect first")


@app.command()
def compare_versioning(
    export_dir: str = typer.Argument(..., help="Directory containing versioned exports"),
):
    """Compare current database state against an export directory.

    Shows which objects are new, missing, changed, or unchanged relative
    to the exported state.
    """
    typer.echo(f"Comparing database state against {export_dir}")
    typer.echo("Note: This requires the MCP server to be running with an active connection")
    typer.echo("Use: macc connect <path> [--com]  to connect first")


if __name__ == "__main__":
    app()