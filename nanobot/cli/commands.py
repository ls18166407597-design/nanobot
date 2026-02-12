"""CLI commands for nanobot."""

import asyncio
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from nanobot import __logo__, __version__
from nanobot.process import CommandLane

app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} nanobot - Personal AI Assistant",
    no_args_is_help=True,
)

from nanobot.cli.config import app as config_app
from nanobot.cli.new import app as new_app
from nanobot.cli.doctor import app as doctor_app
from nanobot.cli import runtime_commands

app.add_typer(config_app, name="config")
app.add_typer(new_app, name="new")
app.add_typer(doctor_app, name="doctor")

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} nanobot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(None, "--version", "-v", callback=version_callback, is_eager=True),
):
    """nanobot - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize nanobot configuration and workspace."""
    from nanobot.config.loader import get_config_path, save_config
    from nanobot.config.schema import Config
    from nanobot.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()

    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")

    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")

    # Create default bootstrap files
    _create_workspace_templates(workspace)

    console.print(f"\n{__logo__} nanobot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]config.json[/cyan] in the data directory")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print('  2. Chat: [cyan]nanobot agent -m "Hello!"[/cyan]')
    console.print(
        "\n[dim]Want Telegram/WhatsApp? See: https://github.com/HKUDS/nanobot#-chat-apps[/dim]"
    )


def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in your memory files
""",
        "SOUL.md": """# Soul

I am nanobot, a lightweight AI assistant.

## Personality

- Helpful and friendly
- Concise and to the point
- Curious and eager to learn

## Values

- Accuracy over speed
- User privacy and safety
- Transparency in actions
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }

    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")

    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")

    # Create EXAMPLES.md
    examples_file = workspace / "EXAMPLES.md"
    if not examples_file.exists():
        examples_file.write_text("""# 快速上手建议 (Quick Start)

老板，您可以尝试输入以下命令来体验我的能力：

1. **GitHub 助手**：`帮我列出 nanobot 项目最近的 5 个 issue`
2. **网页总结**：`总结一下这个网页的内容：https://github.com/HKUDS/nanobot`
3. **天气查询**：`今天北京天气怎么样？适合出门吗？`

您可以直接在聊天窗口输入这些指令。
""")
        console.print("  [dim]Created EXAMPLES.md[/dim]")


# ============================================================================
# Logging / Diagnostics
# ============================================================================


@app.command()
def logs(
    audit: bool = typer.Option(False, "--audit", "-a", help="Show audit log instead of gateway log"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
):
    """View and follow nanobot logs."""
    runtime_commands.cmd_logs(console=console, audit=audit, lines=lines, follow=follow)


@app.command("tools-health")
def tools_health(
    lines: int = typer.Option(5000, "--lines", "-n", help="Number of audit lines to analyze"),
):
    """Show tool health dashboard (calls/failure/timeout/empty-reply)."""
    runtime_commands.cmd_tools_health(console=console, lines=lines)


# ============================================================================
# Runtime Snapshot Compatibility
# ============================================================================

def _collect_health_snapshot(config: Any, data_dir: Path, config_path: Path) -> dict[str, Any]:
    """Compatibility wrapper for tests and external imports."""
    return runtime_commands.collect_health_snapshot(
        config=config, data_dir=data_dir, config_path=config_path
    )


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick connectivity check"),
):
    """Run system health checks."""
    runtime_commands.cmd_check(verbose=verbose, quick=quick)


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the nanobot gateway."""
    runtime_commands.cmd_gateway(console=console, logo=__logo__, port=port, verbose=verbose)


@app.command()
def stop(
    timeout: float = typer.Option(8.0, "--timeout", help="Graceful stop timeout in seconds"),
    force: bool = typer.Option(True, "--force/--no-force", help="Send SIGKILL if graceful stop times out"),
):
    """Stop the nanobot gateway process."""
    runtime_commands.cmd_stop(console=console, timeout=timeout, force=force)


@app.command()
def restart(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    timeout: float = typer.Option(8.0, "--timeout", help="Graceful stop timeout in seconds"),
    force: bool = typer.Option(True, "--force/--no-force", help="Send SIGKILL if graceful stop times out"),
):
    """Restart the nanobot gateway process."""
    runtime_commands.cmd_restart(
        console=console, logo=__logo__, port=port, verbose=verbose, timeout=timeout, force=force
    )


# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
):
    """Interact with the agent directly."""
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.config.loader import load_config, get_data_dir, get_config_path
    from nanobot.providers.factory import ProviderFactory

    data_dir = get_data_dir()
    config_path = get_config_path()
    
    # Environment summary (brief)
    console.print(f"[dim]Data: {data_dir} | Config: {config_path}[/dim]")
    config = load_config()

    api_key = config.get_api_key()
    api_base = config.get_api_base()
    model = config.agents.defaults.model
    
    # Auto-logging setup
    from nanobot.utils.helpers import setup_logging
    setup_logging(level="INFO") # Default for agent command
    
    # Quick connectivity check for first run or when model might be unreachable
    from nanobot.cli.doctor import check as run_health_check
    run_health_check(quick=True)

    key_info = config.get_api_key_info(model)
    api_key = key_info["key"]
    key_path = key_info["path"]

    if not api_key and not config.agents.defaults.model.startswith("bedrock/"):
        console.print(f"[red]Error: No API key found for model '{model}'.[/red]")
        console.print(f"[yellow]Expected at configuration path: {key_path}[/yellow]")
        console.print("[yellow]Tip: Run 'nanobot config edit' or 'nanobot onboard' to set up your keys.[/yellow]")
        raise typer.Exit(1)

    bus = MessageBus()
    provider = ProviderFactory.get_provider(
        api_key=api_key, api_base=api_base, model=model
    )

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        brain_config=config.brain,
        providers_config=config.providers,
        max_tokens=config.agents.defaults.max_tokens,
        temperature=config.agents.defaults.temperature,
        mac_confirm_mode=config.tools.mac.confirm_mode,
    )

    if message:
        # Single message mode
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            console.print(f"\n{__logo__} {response}")

        asyncio.run(run_once())
    else:
        # Interactive mode
        console.print(f"{__logo__} Interactive mode (Ctrl+C to exit)\n")

        async def run_interactive():
            while True:
                try:
                    user_input = console.input("[bold blue]You:[/bold blue] ")
                    if not user_input.strip():
                        continue

                    response = await agent_loop.process_direct(user_input, session_id)
                    console.print(f"\n{__logo__} {response}\n")
                except KeyboardInterrupt:
                    console.print("\nGoodbye!")
                    break

        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from nanobot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row("WhatsApp", "✓" if wa.enabled else "✗", wa.bridge_url)

    dc = config.channels.discord
    table.add_row("Discord", "✓" if dc.enabled else "✗", dc.gateway_url)

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row("Telegram", "✓" if tg.enabled else "✗", tg_config)

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess

    # User's bridge location
    from nanobot.utils.helpers import get_data_path
    user_bridge = get_data_path() / "bridge"

    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge

    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)

    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # nanobot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)

    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge

    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall nanobot")
        raise typer.Exit(1)

    console.print(f"{__logo__} Setting up bridge...")

    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))

    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)

        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)

        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)

    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess

    bridge_dir = _get_bridge_dir()

    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")

    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from nanobot.config.loader import get_data_dir, load_config
    from nanobot.cron.service import CronService

    config = load_config()
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(
        store_path,
        default_tz=str(getattr(config.brain, "timezone", "Asia/Shanghai") or "Asia/Shanghai"),
    )

    jobs = service.list_jobs(include_disabled=all)

    if not jobs:
        console.print("No scheduled jobs.")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")

    import time

    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "one-time"

        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000)
            )
            next_run = next_time

        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"

        table.add_row(job.id, job.name, sched, status, next_run)

    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(
        None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"
    ),
):
    """Add a scheduled job."""
    from nanobot.config.loader import get_data_dir, load_config
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronSchedule

    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime

        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)

    config = load_config()
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(
        store_path,
        default_tz=str(getattr(config.brain, "timezone", "Asia/Shanghai") or "Asia/Shanghai"),
    )

    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )

    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from nanobot.config.loader import get_data_dir, load_config
    from nanobot.cron.service import CronService

    config = load_config()
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(
        store_path,
        default_tz=str(getattr(config.brain, "timezone", "Asia/Shanghai") or "Asia/Shanghai"),
    )

    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from nanobot.config.loader import get_data_dir, load_config
    from nanobot.cron.service import CronService

    config = load_config()
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(
        store_path,
        default_tz=str(getattr(config.brain, "timezone", "Asia/Shanghai") or "Asia/Shanghai"),
    )

    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from nanobot.config.loader import get_data_dir, load_config
    from nanobot.cron.service import CronService

    config = load_config()
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(
        store_path,
        default_tz=str(getattr(config.brain, "timezone", "Asia/Shanghai") or "Asia/Shanghai"),
    )

    async def run():
        return await service.run_job(job_id, force=force)

    if asyncio.run(run()):
        console.print("[green]✓[/green] Job executed")
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status(
    snapshot: bool = typer.Option(
        True, "--snapshot/--no-snapshot", help="Show runtime health snapshot"
    ),
):
    """Show nanobot status."""
    runtime_commands.cmd_status(console=console, logo=__logo__, snapshot=snapshot)


@app.command()
def health(
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as failures"),
    require_gateway: bool = typer.Option(False, "--require-gateway", help="Fail when gateway is not running"),
):
    """Run a lightweight operational health check."""
    runtime_commands.cmd_health(console=console, strict=strict, require_gateway=require_gateway)


# ============================================================================
# Provider Commands
# ============================================================================


provider_app = typer.Typer(help="Manage LLM providers")
app.add_typer(provider_app, name="provider")


@provider_app.command("add")
def provider_add(
    name: str = typer.Option(..., "--name", "-n", help="Provider name (e.g. MyAPI)"),
    base_url: str = typer.Option(..., "--url", "-u", help="API Base URL"),
    api_key: str = typer.Option(..., "--key", "-k", help="API Key"),
):
    """Add or update a provider."""
    from nanobot.config.loader import load_config, save_config

    config = load_config()

    # Check if exists
    updated = False
    for p in config.brain.provider_registry:
        if p.get("name") == name:
            p["base_url"] = base_url
            p["api_key"] = api_key
            updated = True
            break

    if not updated:
        config.brain.provider_registry.append(
            {"name": name, "base_url": base_url, "api_key": api_key}
        )

    save_config(config)
    action = "Updated" if updated else "Added"
    console.print(f"[green]✓[/green] {action} provider '{name}'")


@provider_app.command("remove")
def provider_remove(
    name: str = typer.Argument(..., help="Provider name to remove"),
):
    """Remove a provider."""
    from nanobot.config.loader import load_config, save_config

    config = load_config()
    initial_len = len(config.brain.provider_registry)
    config.brain.provider_registry = [
        p for p in config.brain.provider_registry if p.get("name") != name
    ]

    if len(config.brain.provider_registry) < initial_len:
        save_config(config)
        console.print(f"[green]✓[/green] Removed provider '{name}'")
    else:
        console.print(f"[red]Provider '{name}' not found[/red]")


@provider_app.command("list")
def provider_list():
    """List configured providers."""
    from nanobot.config.loader import load_config

    config = load_config()

    if not config.brain.provider_registry:
        console.print("No additional providers configured.")
        return

    table = Table(title="Provider Registry")
    table.add_column("Name", style="cyan")
    table.add_column("Base URL")
    table.add_column("Key (Masked)")

    for p in config.brain.provider_registry:
        key = p.get("api_key", "")
        masked_key = f"{key[:3]}...{key[-3:]}" if len(key) > 6 else "***"
        table.add_row(p.get("name", "N/A"), p.get("base_url", ""), masked_key)

    console.print(table)


@provider_app.command("check")
def provider_check(
    name: str = typer.Argument(None, help="Check specific provider by name"),
    all: bool = typer.Option(False, "--all", "-a", help="Check all providers"),
):
    """Check status and balance of providers."""
    from nanobot.agent.models import ModelRegistry
    from nanobot.agent.tools.provider import ProviderTool
    from nanobot.config.loader import load_config

    config = load_config()
    registry = ModelRegistry()
    tool = ProviderTool(registry=registry)

    # Register providers from config
    for p in config.brain.provider_registry:
        if "api_key" in p and "base_url" in p:
            asyncio.run(
                registry.register(
                    base_url=p["base_url"],
                    api_key=p["api_key"],
                    name=p.get("name"),
                )
            )

    if name:
        # Check specific
        result = asyncio.run(tool.execute(action="check", name=name))
        console.print(result)
    elif all:
        # Check all
        if not config.brain.provider_registry:
            console.print("No providers to check.")
            return
        
        for p in config.brain.provider_registry:
            p_name = p.get("name")
            console.print(f"\n[bold]Checking {p_name}...[/bold]")
            result = asyncio.run(tool.execute(action="check", name=p_name))
            console.print(result)
    else:
        # Default: list registered providers with basic status
        # Just use list command
        provider_list()
        console.print("\nUse [cyan]nanobot provider check --all[/cyan] to verify balances.")


@app.command()
def tools():
    """List available tools and their safety status."""
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.config.loader import load_config
    from nanobot.providers.factory import ProviderFactory

    config = load_config()
    bus = MessageBus()
    
    # Create a dummy provider to initialize the agent
    provider = ProviderFactory.get_provider(
        api_key=config.get_api_key() or "dummy", 
        model=config.agents.defaults.model
    )
    
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        brain_config=config.brain,
        mac_confirm_mode=config.tools.mac.confirm_mode,
    )
    
    metadata = agent.tools.get_all_metadata()
    
    table = Table(title="Available Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Confirm Mode", style="yellow")
    
    for m in metadata:
        confirm_style = "red" if m["confirm_mode"] == "require" else "yellow" if m["confirm_mode"] == "warn" else "green"
        table.add_row(
            m["name"],
            m["description"],
            f"[{confirm_style}]{m['confirm_mode']}[/{confirm_style}]"
        )
        
    console.print(table)
    console.print("\n[dim]Tip: Use 'confirm=true' in tool calls for sensitive actions.[/dim]")


if __name__ == "__main__":
    app()
