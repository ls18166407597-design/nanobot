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

class Diagnostics:
    """System diagnostic utilities."""
    
    @staticmethod
    async def check_playwright() -> tuple[bool, str]:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                await browser.close()
            return True, "Playwright installed"
        except Exception as e:
            return False, f"Playwright error: {str(e)}"

    @staticmethod
    async def check_connectivity(urls: list[str] = ["https://www.google.com", "https://www.baidu.com"]) -> tuple[bool, str]:
        """Check network connectivity with fallback for domestic environments."""
        last_err = ""
        for url in urls:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        site = "Global" if "google" in url else "Domestic"
                        return True, f"Connected ({site})"
            except Exception as e:
                last_err = str(e)
                continue
        return False, f"Network error: {last_err}"

    @staticmethod
    async def check_model_connectivity() -> tuple[bool, str]:
        try:
            config = load_config()
            from nanobot.providers.factory import ProviderFactory
            key_info = config.get_api_key_info()
            api_key = key_info["key"]
            model = key_info.get("model", config.agents.defaults.model) # Use remapped model
            api_base = config.get_api_base(model)
            proxy = config.tools.web.proxy or config.channels.telegram.proxy
            
            context = f"Model: {model} | Base: {api_base or 'default'}"
            if proxy:
                 context += f" | Proxy: {proxy}"

            if not api_key and not model.startswith("bedrock/"):
                return False, f"Missing API Key (Expected at {key_info['path']})"
                
            provider = ProviderFactory.get_provider(api_key=api_key, api_base=api_base, model=model)
            # Attempt a tiny chat request
            resp = await provider.chat(messages=[{"role": "user", "content": "hi"}], tools=[])
            if resp.content or resp.tool_calls:
                return True, f"OK | {context}"
            return False, f"Empty response | {context}"
        except Exception as e:
            # Differentiate error types if possible
            err_msg = str(e)
            if "api_key" in err_msg.lower():
                return False, f"Invalid API Key | {context}"
            if "timeout" in err_msg.lower():
                return False, f"Timeout | {context}"
            return False, f"Error: {err_msg} | {context}"

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Run system health checks."""
    if ctx.invoked_subcommand is None:
        check()

def check(quick: bool = False):
    """Run system health checks."""
    if not quick:
        console.print(f"\n[bold]{'='*20} Nanobot v{__version__} Doctor {'='*20}[/bold]")
    
    # 1. Paths & Environment
    data_path = get_data_path()
    config_path = get_config_path()
    log_path = get_log_path()
    audit_path = get_audit_path()

    if not quick:
        table_paths = Table(title="Paths & Environment", box=None)
        table_paths.add_column("Item", style="cyan")
        table_paths.add_column("Path", style="white")
        table_paths.add_row("Data Directory", str(data_path))
        table_paths.add_row("Config File", str(config_path))
        table_paths.add_row("Gateway Log", str(log_path))
        table_paths.add_row("Audit Log", str(audit_path))
        console.print(table_paths)
    else:
        console.print(f"[dim]Gateway Log: {log_path}[/dim]")
        console.print(f"[dim]Audit Log: {audit_path}[/dim]")

    # 2. Legacy Check
    if not quick:
        home_path = Path("~/.nanobot").expanduser()
        local_path = Path(".") / ".nanobot"
        if home_path.exists() and local_path.exists():
            console.print("[yellow]Warning: Both ~/.nanobot and ./.nanobot exist. Local dir is prioritized.[/yellow]")

    # 3. Health Checks
    table = Table(title="Component Health" if not quick else None, box=None if quick else None)
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
    
    # Playwright (Skip in quick mode if slow)
    if not quick:
        pw_ok, pw_msg = loop.run_until_complete(Diagnostics.check_playwright())
        table.add_row("Playwright", "OK" if pw_ok else "[red]Error[/red]", pw_msg)
    
    # Network
    net_ok, net_msg = loop.run_until_complete(Diagnostics.check_connectivity())
    table.add_row("Network (Google)", "OK" if net_ok else "[red]Error[/red]", net_msg)
    
    # Model
    mod_ok, mod_msg = loop.run_until_complete(Diagnostics.check_model_connectivity())
    table.add_row("Model API", "OK" if mod_ok else "[red]Error[/red]", mod_msg)

    console.print(table)
    if not quick:
        console.print("[dim]Use 'nanobot logs' to view detailed logs.[/dim]\n")
    
    return net_ok and mod_ok

if __name__ == "__main__":
    app()
