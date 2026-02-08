
import sys
import shutil
import typer
import asyncio
from rich.console import Console
from rich.table import Table
from nanobot import __version__

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

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Run system health checks."""
    if ctx.invoked_subcommand is None:
        check()

def check():
    """Run system health checks."""
    console.print(f"Nanobot v{__version__} Doctor")
    
    table = Table(title="Health Check")
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

    # Playwright
    # This needs async
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    pw_ok, pw_msg = loop.run_until_complete(check_playwright())
    status = "OK" if pw_ok else "[red]Error[/red]"
    table.add_row("Playwright", status, pw_msg)

    console.print(table)

if __name__ == "__main__":
    app()
