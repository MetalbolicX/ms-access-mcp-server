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


if __name__ == "__main__":
    app()