import sys
import shutil
import typer
import asyncio
import os
import httpx
from pathlib import Path
from rich.console import Console
from rich.table import Table
from nanobot import __version__
from nanobot.config.loader import get_config_path, load_config
from nanobot.utils.helpers import get_data_path, get_log_path, get_audit_path

app = typer.Typer(help="Diagnose system health.")
console = Console()

async def check_playwright() -> tuple[bool, str]:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            await browser.close()
        return True, "Playwright installed"
    except Exception as e:
        return False, f"Playwright error: {str(e)}"

async def check_connectivity(url: str = "https://www.google.com") -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return True, "Connected"
            return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, f"Error: {str(e)}"

async def check_model_connectivity() -> tuple[bool, str]:
    try:
        config = load_config()
        from nanobot.providers.factory import ProviderFactory
        api_key = config.get_api_key()
        api_base = config.get_api_base()
        model = config.agents.defaults.model
        
        if not api_key and not model.startswith("bedrock/"):
            return False, "No API key"
            
        provider = ProviderFactory.get_provider(api_key=api_key, api_base=api_base, model=model)
        # Attempt a tiny chat request
        resp = await provider.chat(messages=[{"role": "user", "content": "hi"}], tools=[])
        if resp.content or resp.tool_calls:
            return True, f"Model {model} OK"
        return False, "Empty response"
    except Exception as e:
        return False, f"Model error: {str(e)}"

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Run system health checks."""
    if ctx.invoked_subcommand is None:
        check()

def check():
    """Run system health checks."""
    console.print(f"\n[bold]{'='*20} Nanobot v{__version__} Doctor {'='*20}[/bold]")
    
    # 1. Paths & Environment
    table_paths = Table(title="Paths & Environment", box=None)
    table_paths.add_column("Item", style="cyan")
    table_paths.add_column("Path", style="white")
    
    data_path = get_data_path()
    config_path = get_config_path()
    log_path = get_log_path()
    audit_path = get_audit_path()
    
    table_paths.add_row("Data Directory", str(data_path))
    table_paths.add_row("Config File", str(config_path))
    table_paths.add_row("Gateway Log", str(log_path))
    table_paths.add_row("Audit Log", str(audit_path))
    
    console.print(table_paths)

    # 2. Legacy Check
    home_path = Path("~/.nanobot").expanduser()
    local_path = Path(".") / ".nanobot"
    if home_path.exists() and local_path.exists():
        console.print("[yellow]Warning: Both ~/.nanobot and ./.nanobot exist. Local dir is prioritized.[/yellow]")

    # 3. Health Checks
    table = Table(title="Component Health")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="white")

    # Python Version
    py_ver = sys.version.split()[0]
    table.add_row("Python", "OK", f"v{py_ver}")

    # Git
    if shutil.which("git"):
        table.add_row("Git", "OK", "Installed")
    else:
        table.add_row("Git", "[red]Missing[/red]", "Install git")

    # Run async checks
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Playwright
    pw_ok, pw_msg = loop.run_until_complete(check_playwright())
    table.add_row("Playwright", "OK" if pw_ok else "[red]Error[/red]", pw_msg)
    
    # Network
    net_ok, net_msg = loop.run_until_complete(check_connectivity())
    table.add_row("Network (Google)", "OK" if net_ok else "[red]Error[/red]", net_msg)
    
    # Model
    mod_ok, mod_msg = loop.run_until_complete(check_model_connectivity())
    table.add_row("Model API", "OK" if mod_ok else "[red]Error[/red]", mod_msg)

    console.print(table)
    console.print("[dim]Use 'nanobot logs' to view detailed logs.[/dim]\n")

if __name__ == "__main__":
    app()
