"""Runtime and operational CLI command implementations."""

import asyncio
from pathlib import Path
from typing import Any

import typer
from rich.table import Table

from nanobot.process import CommandLane


def cmd_logs(console, audit: bool, lines: int, follow: bool) -> None:
    """View and follow nanobot logs."""
    from nanobot.utils.helpers import get_audit_path, get_log_path

    path = get_audit_path() if audit else get_log_path()

    if not path.exists():
        console.print(f"[red]Log file not found at {path}[/red]")
        return

    import time

    def print_last_n(p: Path, n: int) -> None:
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
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    console.print(line.strip())
        except KeyboardInterrupt:
            pass


def _check_pid_lock(console, pid_file: Path) -> None:
    """Check if another instance is already running via PID file."""
    from loguru import logger

    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            import os
            import sys

            os.kill(old_pid, 0)
            logger.warning(f"Conflict detected: Another instance with PID {old_pid} is running.")
            console.print(f"[red]Error: Another Nanobot instance (PID {old_pid}) is already running.[/red]")
            console.print(f"[yellow]If you are sure it is not running, delete {pid_file} and try again.[/yellow]")
            sys.exit(1)
        except (ValueError, OSError):
            logger.debug(f"Stale PID file found at {pid_file}, ignoring.")


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


def _stop_gateway_process(
    console, pid_file: Path, timeout: float, force: bool, quiet: bool = False
) -> tuple[bool, int | None]:
    """Stop gateway process from pid file."""
    import os
    import signal
    import time

    if not pid_file.exists():
        if not quiet:
            console.print("[yellow]Gateway is not running (pid file not found).[/yellow]")
        return True, None

    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        _remove_pid_lock(pid_file)
        if not quiet:
            console.print("[yellow]Found invalid pid file. Removed stale lock.[/yellow]")
        return True, None

    try:
        os.kill(pid, 0)
    except OSError:
        _remove_pid_lock(pid_file)
        if not quiet:
            console.print(f"[yellow]Gateway PID {pid} is not alive. Removed stale lock.[/yellow]")
        return True, pid

    if not quiet:
        console.print(f"[cyan]Stopping gateway process {pid}...[/cyan]")
    os.kill(pid, signal.SIGTERM)

    deadline = time.time() + max(0.1, timeout)
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
            time.sleep(0.2)
        except OSError:
            _remove_pid_lock(pid_file)
            if not quiet:
                console.print(f"[green]Gateway stopped (pid={pid}).[/green]")
            return True, pid

    if force:
        if not quiet:
            console.print(f"[yellow]Graceful stop timed out. Sending SIGKILL to {pid}...[/yellow]")
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        time.sleep(0.2)
        try:
            os.kill(pid, 0)
            if not quiet:
                console.print(f"[red]Failed to stop gateway process {pid}.[/red]")
            return False, pid
        except OSError:
            _remove_pid_lock(pid_file)
            if not quiet:
                console.print(f"[green]Gateway force-stopped (pid={pid}).[/green]")
            return True, pid

    if not quiet:
        console.print(f"[red]Gateway still running (pid={pid}).[/red]")
    return False, pid


def _print_gateway_env_summary(console, data_dir: Path, config_path: Path, workspace_path: str, log_path: Path) -> None:
    """Print a concise runtime environment table for gateway startup."""
    table = Table(box=None, padding=(0, 2))
    table.add_column("Env Item", style="cyan")
    table.add_column("Path", style="dim")
    table.add_row("Data Dir", str(data_dir))
    table.add_row("Config", str(config_path))
    table.add_row("Workspace", workspace_path)
    table.add_row("Logs", str(log_path))
    console.print(table)


def _prepare_gateway_runtime(verbose: bool):
    """Load startup config and initialize logging/health checks."""
    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    from nanobot.cli.doctor import check as run_health_check
    from nanobot.config.loader import get_config_path, load_config
    from nanobot.utils.helpers import get_log_path, setup_logging

    config = load_config()
    config_path = get_config_path()
    log_path = get_log_path()
    setup_logging(level="DEBUG" if verbose else "INFO")
    run_health_check(quick=True)
    return config, config_path, log_path


def collect_health_snapshot(config: Any, data_dir: Path, config_path: Path) -> dict[str, Any]:
    """Collect a lightweight runtime/configuration health snapshot."""
    import json
    import os
    from collections import Counter

    workspace = Path(str(config.workspace_path)).expanduser()
    pid_file = data_dir / "gateway.pid"

    pid = None
    gateway_running = False
    stale_pid = False
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            gateway_running = True
        except Exception:
            stale_pid = True
            gateway_running = False

    model = config.agents.defaults.model
    key_info = config.get_api_key_info(model)
    model_key_present = bool(key_info.get("key")) or model.startswith("bedrock/")

    recent_errors = 0
    error_types: Counter[str] = Counter()
    audit_path = data_dir / "audit.log"
    if audit_path.exists():
        try:
            lines = audit_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-500:]
            for line in lines:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                etype = str(event.get("type", ""))
                status_val = str(event.get("status", ""))
                if (etype == "tool_end" and status_val == "error") or etype.endswith("_error"):
                    recent_errors += 1
                    error_types[etype] += 1
        except Exception:
            pass

    return {
        "config_exists": config_path.exists(),
        "workspace_exists": workspace.exists(),
        "gateway_running": gateway_running,
        "pid": pid,
        "stale_pid": stale_pid,
        "telegram_enabled": bool(config.channels.telegram.enabled),
        "telegram_token_set": bool(config.channels.telegram.token),
        "model": model,
        "model_key_present": model_key_present,
        "provider_registry_count": len(config.brain.provider_registry or []),
        "recent_errors": recent_errors,
        "error_types": dict(error_types),
    }


def cmd_check(verbose: bool, quick: bool) -> None:
    """Run system health checks."""
    from nanobot.cli.doctor import check as run_checks

    _ = verbose
    run_checks(quick=quick)


def cmd_gateway(console, logo: str, port: int, verbose: bool) -> None:
    """Start the nanobot gateway."""
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.channels.manager import ChannelManager
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    from nanobot.providers.factory import ProviderFactory

    data_dir = get_data_dir()
    pid_file = data_dir / "gateway.pid"
    _check_pid_lock(console, pid_file)
    _write_pid_lock(pid_file)

    config, config_path, log_path = _prepare_gateway_runtime(verbose)
    _print_gateway_env_summary(
        console=console,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=str(config.workspace_path),
        log_path=log_path,
    )
    console.print(f"{logo} Starting nanobot gateway on port {port}...")

    model = config.agents.defaults.model
    is_bedrock = "bedrock" in model.lower()

    bus = MessageBus()
    key_info = config.get_api_key_info(model)
    api_key = key_info["key"]
    model = key_info.get("model", model)
    key_path = key_info["path"]
    api_base = config.get_api_base(model)

    if not api_key and not is_bedrock:
        console.print(f"[red]Error: No API key found for model '{model}'.[/red]")
        console.print(f"[yellow]Expected at configuration path: {key_path}[/yellow]")
        console.print("[yellow]Tip: Run 'nanobot config edit' or 'nanobot onboard' to set up your keys.[/yellow]")
        raise typer.Exit(1)

    provider = ProviderFactory.get_provider(api_key=api_key, api_base=api_base, model=model)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    web_proxy = config.tools.web.proxy or config.channels.telegram.proxy

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

    async def on_cron_job(job: CronJob) -> str | None:
        from nanobot.utils.helpers import audit_log
        from nanobot.bus.events import OutboundMessage

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

    async def on_heartbeat(prompt: str) -> str:
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
            await asyncio.gather(agent.run(), channels.start_all())
        except (KeyboardInterrupt, asyncio.CancelledError):
            console.print("\nShutting down...")
        finally:
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
            _remove_pid_lock(pid_file)

    asyncio.run(run())


def cmd_stop(console, timeout: float, force: bool) -> None:
    """Stop the nanobot gateway process."""
    from nanobot.config.loader import get_data_dir

    data_dir = get_data_dir()
    pid_file = data_dir / "gateway.pid"
    stopped, _pid = _stop_gateway_process(console=console, pid_file=pid_file, timeout=timeout, force=force)
    if not stopped:
        raise typer.Exit(1)


def cmd_restart(console, logo: str, port: int, verbose: bool, timeout: float, force: bool) -> None:
    """Restart the nanobot gateway process."""
    from nanobot.config.loader import get_data_dir

    data_dir = get_data_dir()
    pid_file = data_dir / "gateway.pid"
    stopped, _pid = _stop_gateway_process(
        console=console, pid_file=pid_file, timeout=timeout, force=force, quiet=False
    )
    if not stopped:
        raise typer.Exit(1)

    console.print("[cyan]Starting gateway...[/cyan]")
    cmd_gateway(console=console, logo=logo, port=port, verbose=verbose)


def cmd_status(console, logo: str, snapshot: bool = True) -> None:
    """Show nanobot status."""
    import json
    import os
    from collections import Counter

    from nanobot.config.loader import get_config_path, get_data_dir, load_config

    config_path = get_config_path()
    data_dir = get_data_dir()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{logo} nanobot Status\n")
    console.print(
        f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}"
    )
    console.print(
        f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}"
    )

    if config_path.exists():
        console.print(f"Model: {config.agents.defaults.model}")
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
            f"[green]✓ {config.providers.vllm.api_base}[/green]" if has_vllm else "[dim]not set[/dim]"
        )
        console.print(f"vLLM/Local: {vllm_status}")

    if not snapshot:
        return

    console.print("\n[bold]Runtime Snapshot[/bold]")
    pid_file = data_dir / "gateway.pid"
    pid = None
    gateway_alive = False
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            gateway_alive = True
        except Exception:
            gateway_alive = False
    console.print(
        f"Gateway: {'[green]running[/green]' if gateway_alive else '[yellow]stopped[/yellow]'}"
        + (f" (pid={pid})" if pid else "")
    )
    sessions_dir = data_dir / "sessions"
    session_count = len(list(sessions_dir.glob("*.jsonl"))) if sessions_dir.exists() else 0
    console.print(f"Sessions: {session_count}")
    reg_count = len(config.brain.provider_registry or [])
    console.print(f"Provider Registry: {reg_count} configured")
    if reg_count:
        for p in (config.brain.provider_registry or [])[:5]:
            name = p.get("name", "unknown")
            model = p.get("model") or p.get("default_model") or "-"
            base = p.get("base_url") or p.get("api_base") or "-"
            console.print(f"  - {name} | model={model} | base={base}")

    audit_path = data_dir / "audit.log"
    recent_errors = 0
    error_types: Counter[str] = Counter()
    if audit_path.exists():
        try:
            lines = audit_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-500:]
            for line in lines:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                etype = str(event.get("type", ""))
                status_val = str(event.get("status", ""))
                if (etype == "tool_end" and status_val == "error") or etype.endswith("_error"):
                    recent_errors += 1
                    error_types[etype] += 1
        except Exception:
            pass
    console.print(f"Recent Errors (last 500 audit events): {recent_errors}")
    if error_types:
        for etype, cnt in error_types.most_common(5):
            console.print(f"  - {etype}: {cnt}")


def cmd_health(console, strict: bool, require_gateway: bool) -> None:
    """Run a lightweight operational health check."""
    from nanobot.config.loader import get_config_path, get_data_dir, load_config

    data_dir = get_data_dir()
    config_path = get_config_path()
    config = load_config()
    snap = collect_health_snapshot(config=config, data_dir=data_dir, config_path=config_path)

    checks = Table(box=None, padding=(0, 2))
    checks.add_column("Check", style="cyan")
    checks.add_column("Status")
    checks.add_column("Detail", style="dim")

    checks.add_row("Config file", "OK" if snap["config_exists"] else "FAIL", str(config_path))
    checks.add_row("Workspace", "OK" if snap["workspace_exists"] else "FAIL", str(config.workspace_path))
    checks.add_row("Gateway", "OK" if snap["gateway_running"] else "WARN", f"pid={snap['pid']}" if snap["pid"] else "not running")
    checks.add_row("Telegram", "OK" if (not snap["telegram_enabled"] or snap["telegram_token_set"]) else "FAIL", "enabled" if snap["telegram_enabled"] else "disabled")
    checks.add_row("Model key", "OK" if snap["model_key_present"] else "FAIL", snap["model"])
    checks.add_row("Recent errors", "OK" if snap["recent_errors"] == 0 else "WARN", str(snap["recent_errors"]))
    checks.add_row("Provider registry", "OK" if snap["provider_registry_count"] > 0 else "WARN", str(snap["provider_registry_count"]))
    console.print(checks)

    failures: list[str] = []
    warnings: list[str] = []
    if not snap["config_exists"]:
        failures.append("config file missing")
    if not snap["workspace_exists"]:
        failures.append("workspace missing")
    if not snap["model_key_present"]:
        failures.append("model key missing")
    if snap["telegram_enabled"] and not snap["telegram_token_set"]:
        failures.append("telegram enabled but bot token is empty")
    if require_gateway and not snap["gateway_running"]:
        failures.append("gateway is not running")

    if not snap["gateway_running"]:
        warnings.append("gateway is not running")
    if snap["stale_pid"]:
        warnings.append("pid file exists but process is not alive")
    if snap["recent_errors"] > 0:
        warnings.append(f"recent errors={snap['recent_errors']}")
    if snap["provider_registry_count"] == 0:
        warnings.append("provider registry is empty")

    if failures:
        console.print(f"[red]Health check failed:[/red] {', '.join(failures)}")
        raise typer.Exit(1)

    if warnings:
        console.print(f"[yellow]Health warnings:[/yellow] {', '.join(warnings)}")
        if strict:
            raise typer.Exit(1)

    console.print("[green]Health check passed.[/green]")
