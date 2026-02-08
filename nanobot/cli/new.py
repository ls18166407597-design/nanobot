
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
    # Assume we are in a workspace or project root
    # Try to find .agent/skills or nanobot/skills
    
    # Simple heuristic: if .agent/skills exists, use it. Else check nanobot/skills.
    # Otherwise create in current dir/skills
    
    target_dir = Path(".agent/skills")
    if not target_dir.exists():
        target_dir = Path("nanobot/skills")
    
    if not target_dir.exists():
        target_dir = Path("skills")
        target_dir.mkdir(exist_ok=True)
        
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
