
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
    import json
    try:
        # Use json.loads to support bool, int, float, list, dict, and null
        val = json.loads(value)
    except json.JSONDecodeError:
        # Fallback to string if not valid JSON/number/bool
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
    """Validate configuration file against the schema."""
    from nanobot.config.loader import load_config
    config_path = get_config_path()
    if not config_path.exists():
        console.print(f"[red]No configuration found at {config_path}.[/red]")
        raise typer.Exit(1)
        
    try:
        # load_config internals use Config.model_validate
        load_config(config_path)
        console.print(f"[green]✓[/green] Configuration at {config_path} is valid.")
    except Exception as e:
        console.print(f"[red]❌ Configuration validation failed:[/red]")
        console.print(f"[dim]{str(e)}[/dim]")
        raise typer.Exit(1)

@app.command("edit")
def edit_config():
    """Open the configuration file in your default system editor."""
    import os
    import subprocess
    import platform

    config_path = get_config_path()
    if not config_path.exists():
        console.print(f"[red]No configuration found at {config_path}. Run 'nanobot onboard' first.[/red]")
        raise typer.Exit(1)

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    
    if not editor:
        if platform.system() == "Darwin":
            editor = "open"
        elif platform.system() == "Windows":
            editor = "notepad"
        else:
            # Linux fallback
            for e in ["nano", "vi", "vim"]:
                if subprocess.run(["which", e], capture_output=True).returncode == 0:
                    editor = e
                    break
    
    if not editor:
        console.print("[red]No editor found. Please set the EDITOR environment variable.[/red]")
        console.print(f"Manual edit path: [cyan]{config_path}[/cyan]")
        raise typer.Exit(1)

    console.print(f"Opening [cyan]{config_path}[/cyan] with [green]{editor}[/green]...")
    try:
        if editor == "open":
            # macOS open uses default app association
            subprocess.run([editor, str(config_path)], check=True)
        else:
            subprocess.run([editor, str(config_path)], check=True)
    except Exception as e:
        console.print(f"[red]Failed to open editor: {e}[/red]")
        console.print(f"Manual edit path: [cyan]{config_path}[/cyan]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
