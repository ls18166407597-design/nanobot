
import os
import typer
from pathlib import Path
from rich.console import Console

app = typer.Typer(help="Scaffold new components.")
console = Console()

TEMPLATE_SKILL = """---
description: {description}
---

# {name}

{description}

## Usage
...
"""

@app.command("skill")
def new_skill(name: str, description: str = "A new skill"):
    """Create a new skill."""
    # Canonical target: workspace skills.
    # Keep compatibility with existing ".agent/skills" projects.
    target_dir = Path("workspace/skills")
    if not target_dir.exists() and Path(".agent/skills").exists():
        target_dir = Path(".agent/skills")
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        
    skill_dir = target_dir / name
    if skill_dir.exists():
        console.print(f"[red]Skill {name} already exists at {skill_dir}[/red]")
        raise typer.Exit(1)
        
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    
    with open(skill_file, "w") as f:
        f.write(TEMPLATE_SKILL.format(name=name, description=description))
        
    console.print(f"[green]Created new skill at {skill_file}[/green]")

if __name__ == "__main__":
    app()
