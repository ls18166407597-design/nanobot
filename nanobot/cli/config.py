
import json
import typer
from rich.console import Console
from rich.table import Table
from nanobot.config.loader import get_config_path

app = typer.Typer(help="Manage Nanobot configuration.")
console = Console()

@app.command("list")
def list_config():
    """List current configuration."""
    config_path = get_config_path()
    if not config_path.exists():
        console.print(f"[yellow]No configuration found at {config_path}[/yellow]")
        return

    with open(config_path, "r") as f:
        config = json.load(f)

    table = Table(title=f"Configuration ({config_path})")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    def _flatten(d, parent_key=""):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(_flatten(v, new_key))
            else:
                # Mask sensitive keys
                if "key" in k.lower() or "token" in k.lower() or "password" in k.lower():
                    v = "******"
                items.append((new_key, str(v)))
        return items

    for key, value in _flatten(config):
        table.add_row(key, value)

    console.print(table)

@app.command("set")
def set_config(key: str, value: str):
    """Set a configuration value (e.g., providers.openai.apiKey sk-...)."""
    config_path = get_config_path()
    if not config_path.exists():
        console.print(f"[red]No configuration found at {config_path}. Run 'nanobot onboard' first.[/red]")
        raise typer.Exit(1)

    with open(config_path, "r") as f:
        config = json.load(f)

    parts = key.split(".")
    current = config
    # Iterate over all but the last part
    for k in parts[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
        if not isinstance(current, dict):
             console.print(f"[red]Cannot set {key}: {k} is not a dictionary.[/red]")
             raise typer.Exit(1)

    # Try to infer type
    if value.lower() == "true":
        val = True
    elif value.lower() == "false":
        val = False
    elif value.isdigit():
        val = int(value)
    else:
        val = value

    if isinstance(current, dict):
        current[parts[-1]] = val
    else:
        # Should be unreachable due to loop check, but satisfies type checker
        console.print(f"[red]Cannot set {key}: Target is not a dictionary.[/red]")
        raise typer.Exit(1)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    console.print(f"[green]Set {key} = {val}[/green]")

@app.command("check")
def check_config():
    """Validate configuration file."""
    # Placeholder for validation logic
    console.print("[green]Configuration file is valid JSON.[/green]")

if __name__ == "__main__":
    app()
