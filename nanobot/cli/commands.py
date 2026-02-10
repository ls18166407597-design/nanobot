"""CLI commands for nanobot."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from nanobot import __logo__, __version__

app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} nanobot - Personal AI Assistant",
    no_args_is_help=True,
)

from nanobot.cli.config import app as config_app
from nanobot.cli.new import app as new_app
from nanobot.cli.doctor import app as doctor_app

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
    from nanobot.utils.helpers import get_log_path, get_audit_path
    
    path = get_audit_path() if audit else get_log_path()
    
    if not path.exists():
        console.print(f"[red]Log file not found at {path}[/red]")
        return

    import time
    
    def print_last_n(p, n):
        with open(p, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            for line in all_lines[-n:]:
                console.print(line.strip())

    console.print(f"[dim]Log path: {path}[/dim]")
    print_last_n(path, lines)
    
    if follow:
        console.print(f"\n[bold green]Following {path.name}...[/bold green] (Ctrl+C to stop)")
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.seek(0, 2) # Go to end
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    console.print(line.strip())
        except KeyboardInterrupt:
            pass


# ============================================================================
# Process Management Helpers
# ============================================================================

def _check_pid_lock(pid_file: Path) -> None:
    """Check if another instance is already running via PID file."""
    from loguru import logger
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            # Check if process is still alive
            import os
            import sys
            os.kill(old_pid, 0)
            logger.warning(f"Conflict detected: Another instance with PID {old_pid} is running.")
            console.print(f"[red]Error: Another Nanobot instance (PID {old_pid}) is already running.[/red]")
            console.print(f"[yellow]If you are sure it is not running, delete {pid_file} and try again.[/yellow]")
            sys.exit(1)
        except (ValueError, OSError):
            # Stale PID file or process not found, safe to overwrite
            logger.debug(f"Stale PID file found at {pid_file}, ignoring.")
            pass

def _write_pid_lock(pid_file: Path) -> None:
    """Write current PID to lock file."""
    import os
    pid_file.write_text(str(os.getpid()))

def _remove_pid_lock(pid_file: Path) -> None:
    """Remove PID lock file."""
    if pid_file.exists():
        try:
            pid_file.unlink()
        except Exception:
            pass


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick connectivity check"),
):
    """Run system health checks."""
    from nanobot.cli.doctor import check as run_checks
    run_checks(quick=quick)


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the nanobot gateway."""
    from nanobot.config.loader import get_data_dir, load_config
    data_dir = get_data_dir()
    pid_file = data_dir / "gateway.pid"
    _check_pid_lock(pid_file)
    _write_pid_lock(pid_file)

    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.channels.manager import ChannelManager
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    from nanobot.providers.factory import ProviderFactory

    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    from nanobot.config.loader import load_config, get_data_dir, get_config_path
    from nanobot.utils.helpers import get_log_path
    from nanobot.providers.factory import ProviderFactory
    from nanobot.bus.queue import MessageBus
    from nanobot.cron.service import CronService

    data_dir = get_data_dir()
    config_path = get_config_path()
    log_path = get_log_path()
    
    # Environment summary table
    table = Table(box=None, padding=(0, 2))
    table.add_column("Env Item", style="cyan")
    table.add_column("Path", style="dim")
    table.add_row("Data Dir", str(data_dir))
    table.add_row("Config", str(config_path))
    table.add_row("Workspace", str(load_config().workspace_path))
    table.add_row("Logs", str(log_path))
    console.print(table)
    
    # Auto-logging setup
    from nanobot.utils.helpers import setup_logging
    setup_logging(level="DEBUG" if verbose else "INFO")
    
    # Quick health check
    from nanobot.cli.doctor import check as run_health_check
    run_health_check(quick=True)
    
    console.print(f"{__logo__} Starting nanobot gateway on port {port}...")

    config = load_config()
    model = config.agents.defaults.model
    is_bedrock = "bedrock" in model.lower()

    # Create components
    bus = MessageBus()

    # Create provider (via factory)
    key_info = config.get_api_key_info(model)
    api_key = key_info["key"]
    model = key_info.get("model", model)  # Remap alias to real model name
    key_path = key_info["path"]
    api_base = config.get_api_base(model)

    if not api_key and not is_bedrock:
        console.print(f"[red]Error: No API key found for model '{model}'.[/red]")
        console.print(f"[yellow]Expected at configuration path: {key_path}[/yellow]")
        console.print("[yellow]Tip: Run 'nanobot config edit' or 'nanobot onboard' to set up your keys.[/yellow]")
        raise typer.Exit(1)

    provider = ProviderFactory.get_provider(
        api_key=api_key, api_base=api_base, model=model
    )

    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    # Determine web proxy (prefer tools.web.proxy, fallback to telegram channel proxy)
    web_proxy = config.tools.web.proxy or config.channels.telegram.proxy

    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        brain_config=config.brain,
        providers_config=config.providers,
        web_proxy=web_proxy,
        max_tokens=config.agents.defaults.max_tokens,
        temperature=config.agents.defaults.temperature,
        mac_confirm_mode=config.tools.mac.confirm_mode,
    )

    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        from nanobot.utils.helpers import audit_log
        audit_log("cron_start", {"job_id": job.id, "message": job.payload.message})
        
        try:
            response = await agent.process_direct(
                job.payload.message,
                session_key=f"cron:{job.id}",
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to or "direct",
                lane=CommandLane.BACKGROUND,
            )
            
            audit_log("cron_complete", {"job_id": job.id, "success": True})

            if job.payload.deliver and job.payload.to:
                from nanobot.bus.events import OutboundMessage

                await bus.publish_outbound(
                    OutboundMessage(
                        channel=job.payload.channel or "cli",
                        chat_id=job.payload.to,
                        content=response or "",
                    )
                )
            return response
        except Exception as e:
            audit_log("cron_error", {"job_id": job.id, "error": str(e)})
            raise

    cron.on_job = on_cron_job

    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        from nanobot.utils.helpers import audit_log
        audit_log("heartbeat_start", {})
        try:
            response = await agent.process_direct(prompt, session_key="heartbeat", lane=CommandLane.BACKGROUND)
            tag = "OK" if "HEARTBEAT_OK" in (response or "").upper() else "TASK"
            audit_log("heartbeat_complete", {"result": tag})
            return response
        except Exception as e:
            audit_log("heartbeat_error", {"error": str(e)})
            raise

    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=config.brain.heartbeat_interval,
        enabled=config.brain.heartbeat_enabled,
    )

    # Create channel manager
    channels = ChannelManager(config, bus)

    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")

    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")

    if config.brain.heartbeat_enabled:
        console.print(f"[green]✓[/green] Heartbeat: every {config.brain.heartbeat_interval//60}m")
    else:
        console.print("[dim]Heartbeat: disabled[/dim]")

    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            console.print("\nShutting down...")
        finally:
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
            _remove_pid_lock(pid_file)

    asyncio.run(run())


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
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

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
    from nanobot.config.loader import get_data_dir
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

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

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
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

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
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

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
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

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
def status():
    """Show nanobot status."""
    from nanobot.config.loader import get_config_path, load_config

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} nanobot Status\n")

    console.print(
        f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}"
    )
    console.print(
        f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}"
    )

    if config_path.exists():
        console.print(f"Model: {config.agents.defaults.model}")

        # Check API keys
        has_openrouter = bool(config.providers.openrouter.api_key)
        has_anthropic = bool(config.providers.anthropic.api_key)
        has_openai = bool(config.providers.openai.api_key)
        has_gemini = bool(config.providers.gemini.api_key)
        has_vllm = bool(config.providers.vllm.api_base)

        console.print(
            f"OpenRouter API: {'[green]✓[/green]' if has_openrouter else '[dim]not set[/dim]'}"
        )
        console.print(
            f"Anthropic API: {'[green]✓[/green]' if has_anthropic else '[dim]not set[/dim]'}"
        )
        console.print(f"OpenAI API: {'[green]✓[/green]' if has_openai else '[dim]not set[/dim]'}")
        console.print(f"Gemini API: {'[green]✓[/green]' if has_gemini else '[dim]not set[/dim]'}")
        vllm_status = (
            f"[green]✓ {config.providers.vllm.api_base}[/green]"
            if has_vllm
            else "[dim]not set[/dim]"
        )
        console.print(f"vLLM/Local: {vllm_status}")


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


if __name__ == "__main__":
    app()
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
