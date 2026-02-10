import subprocess
from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult, ToolSeverity


class MacTool(Tool):
    """Tool for controlling local macOS system settings and applications."""

    name = "mac_control"
    description = """
    Control macOS system settings and applications.
    Capabilities:
    - Audio: Set/Get volume, mute/unmute.
    - Apps: Open, close, or list running applications.
    - System: specific system info (battery, basic stats).
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "set_volume",
                    "get_volume",
                    "mute",
                    "unmute",
                    "open_app",
                    "close_app",
                    "list_apps",
                    "get_frontmost_app",
                    "activate_app",
                    "battery",
                    "system_stats",
                    "mac_settings",
                ],
                "description": "The action to perform.",
            },
            "sub_action": {
                "type": "string",
                "enum": ["read_default", "write_default", "reveal_pane", "run_shortcut", "get_power_info"],
                "description": "The sub-action for mac_settings.",
            },
            "domain": {
                "type": "string",
                "description": "Domain/Bundle ID for read/write_default (e.g. com.apple.dock).",
            },
            "key": {
                "type": "string",
                "description": "Key for read/write_default.",
            },
            "pane_id": {
                "type": "string",
                "description": "Pane ID for reveal_pane (e.g. com.apple.wifi-settings-extension).",
            },
            "name": {
                "type": "string",
                "description": "Name for run_shortcut.",
            },
            "value": {
                "type": ["string", "integer", "boolean"],
                "description": "Value for the action or sub-action.",
            },
            "confirm": {
                "type": "boolean",
                "description": "Set to true to confirm potentially disruptive actions.",
            },
        },
        "required": ["action"],
    }

    def __init__(self, confirm_mode: str = "warn") -> None:
        self._confirm_mode = confirm_mode
        self._confirm_actions = {
            "set_volume",
            "mute",
            "unmute",
            "open_app",
            "close_app",
            "activate_app",
            "write_default",
        }

    @property
    def confirm_mode(self) -> str:
        """Override base property to return instance value."""
        return self._confirm_mode

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        value = kwargs.get("value")
        confirm = bool(kwargs.get("confirm"))
        warning = None

        try:
            # Type safety: Handled by ToolExecutor

            sub_action = kwargs.get("sub_action")
            if (action in self._confirm_actions or sub_action == "write_default") and not confirm:
                if self.confirm_mode == "require":
                    return ToolResult(
                        success=False,
                        output="Error: Confirmation required for disruptive macOS action (including write_default). Please re-run with 'confirm': true in tool parameters.",
                        severity=ToolSeverity.ERROR,
                        requires_user_confirmation=True,
                    )
                if self.confirm_mode == "warn":
                    warning = "Warning: disruptive macOS action executed without 'confirm': true. This can be strictly required by setting tools.mac.confirm_mode to 'require'."

            result = ""
            if action == "set_volume":
                if value is None:
                    return ToolResult(success=False, output="Error: 'value' (0-100) is required for 'set_volume'.")
                result = self._set_volume(int(value))
            elif action == "get_volume":
                result = self._get_volume()
            elif action == "mute":
                result = self._set_mute(True)
            elif action == "unmute":
                result = self._set_mute(False)
            elif action == "open_app":
                if not value:
                    return ToolResult(success=False, output="Error: App name is required for 'open_app'.")
                result = self._open_app(str(value))
            elif action == "close_app":
                if not value:
                    return ToolResult(success=False, output="Error: App name is required for 'close_app'.")
                result = self._close_app(str(value))
            elif action == "list_apps":
                result = self._list_apps()
            elif action == "get_frontmost_app":
                result = self.get_frontmost_app_info()
            elif action == "activate_app":
                if not value:
                    return ToolResult(success=False, output="Error: App name is required for 'activate_app'.")
                result = self._activate_app(str(value))
            elif action == "battery":
                result = self._get_battery()
            elif action == "system_stats":
                result = self._get_system_stats()
            elif action == "mac_settings":
                result = await self._dispatch_mac_settings(**kwargs)
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}")

            final_output = f"{warning}\n{result}" if warning else result
            is_error = "Error" in final_output or "Failed" in final_output
            
            return ToolResult(
                success=not is_error,
                output=final_output,
                remedy="请检查应用名称是否正确，或系统辅助功能权限是否已开启。" if is_error else None,
                severity=ToolSeverity.ERROR if is_error else ToolSeverity.INFO,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Mac Tool Error: {str(e)}",
                severity=ToolSeverity.ERROR,
            )

    def _run_osascript(self, script: str) -> str:
        cmd = ["osascript", "-e", script]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"AppleScript error: {result.stderr.strip()}")
        return result.stdout.strip()

    def _set_volume(self, level: int) -> str:
        # volume level is 0-100
        if not (0 <= level <= 100):
            return "Error: Volume must be between 0 and 100."
        self._run_osascript(f"set volume output volume {level}")
        return f"Volume set to {level}%."

    def _get_volume(self) -> str:
        vol = self._run_osascript("output volume of (get volume settings)")
        return f"Current volume: {vol}%"

    def _set_mute(self, mute: bool) -> str:
        state = "true" if mute else "false"
        self._run_osascript(f"set volume with output muted {state}")
        return "Muted." if mute else "Unmuted."

    def _open_app(self, app_name: str) -> str:
        # Use 'open -a'
        cmd = ["open", "-a", app_name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Failed to open '{app_name}': {result.stderr.strip()}"
        return f"Opened '{app_name}'."

    def _close_app(self, app_name: str) -> str:
        # Try graceful quit via AppleScript first
        script = f'tell application "{app_name}" to quit'
        try:
            self._run_osascript(script)

            # Verification step: Wait a bit and check if still running
            import time

            time.sleep(2)  # Give it 2 seconds to close

            check_script = (
                f'tell application "System Events" to exists (processes where name is "{app_name}")'
            )
            exists = self._run_osascript(check_script)

            if exists == "true":
                # If still running, maybe try a bit more force? or just report it
                return f"Sent close command to '{app_name}', but it is still running (it might have an unsaved changes dialog)."

            return f"Successfully verified: '{app_name}' has been closed."
        except Exception as e:
            return f"Failed to close '{app_name}': {str(e)}"

    def _list_apps(self) -> str:
        # Get both name and bundle ID for precision
        script = 'tell application "System Events" to get {name, bundle identifier} of (processes where background only is false)'
        raw_output = self._run_osascript(script)
        
        # AppleScript returns a comma-separated list of names followed by a list of IDs
        # Format: "Name1, Name2, ID1, ID2"
        parts = [p.strip() for p in raw_output.split(",")]
        mid = len(parts) // 2
        names = parts[:mid]
        bundle_ids = parts[mid:]
        
        running_apps = []
        for name, bid in zip(names, bundle_ids):
            display_name = name
            # Legacy branding check (optional, keeping it generic)
            if bid == "com.google.nanobot":
                return "Nanobot Bridge"
            running_apps.append(display_name)
            
        return f"Running Apps: {', '.join(running_apps)}"

    def get_frontmost_app_info(self) -> str:
        """Get the name and bundle identifier of the frontmost application."""
        try:
            import AppKit
            workspace = AppKit.NSWorkspace.sharedWorkspace()
            front_app = workspace.frontmostApplication()
            
            if not front_app:
                return "Error: Could not determine frontmost application."
                
            name = front_app.localizedName()
            bundle_id = front_app.bundleIdentifier()
            
            # Specialized detection for Web Apps
            if bundle_id:
                if bundle_id.startswith("com.apple.Safari.WebApp"):
                    return f"App: {name} (Safari Web App) | ID: {bundle_id}"
                if bundle_id.startswith("com.google.Chrome.app"):
                    return f"App: {name} (Chrome Web App) | ID: {bundle_id}"
            
            return f"App: {name} | ID: {bundle_id or 'Unknown'}"
            
        except Exception as e:
            # Fallback to AppleScript if AppKit fails
            script = 'name of (info for (path to frontmost application))'
            try:
                name = self._run_osascript(script)
                return f"App: {name} (Simplified Detection)"
            except:
                return f"Error getting frontmost app: {str(e)}"

    def _activate_app(self, app_name: str) -> str:
        script = f'tell application "{app_name}" to activate'
        try:
            self._run_osascript(script)
            return f"Activated '{app_name}'."
        except Exception as e:
            return f"Failed to activate '{app_name}': {str(e)}"

    def _get_battery(self) -> str:
        result = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
        return result.stdout.strip()

    def _get_system_stats(self) -> str:
        # Simple top summary
        cmd = ["top", "-l", "1", "-n", "0"]  # -l 1 sample, -n 0 lines of processes (header only)
        result = subprocess.run(cmd, capture_output=True, text=True)
        # top header contains the info
        lines = result.stdout.splitlines()[:15]  # Grab first few lines
        return "\n".join(lines)

    async def _dispatch_mac_settings(self, **kwargs: Any) -> str:
        sub_action = kwargs.get("sub_action")
        if not sub_action:
            return "Error: 'sub_action' is required for 'mac_settings'."

        if sub_action == "read_default":
            return self._read_default(kwargs.get("domain"), kwargs.get("key"))
        elif sub_action == "write_default":
            return self._write_default(kwargs.get("domain"), kwargs.get("key"), kwargs.get("value"))
        elif sub_action == "reveal_pane":
            return self._reveal_pane(kwargs.get("pane_id"))
        elif sub_action == "run_shortcut":
            return self._run_shortcut(kwargs.get("name"))
        elif sub_action == "get_power_info":
            return self._get_detailed_power()
        else:
            return f"Error: Unknown sub_action '{sub_action}'."

    def _read_default(self, domain: str | None, key: str | None) -> str:
        if not domain or not key:
            return "Error: 'domain' and 'key' are required for 'read_default'."
        cmd = ["defaults", "read", str(domain), str(key)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Failed to read default '{domain} {key}': {result.stderr.strip()}"
        return result.stdout.strip()

    def _write_default(self, domain: str | None, key: str | None, value: Any) -> str:
        if not domain or not key or value is None:
            return "Error: 'domain', 'key', and 'value' are required for 'write_default'."
        
        # Determine type for defaults command
        val_type = "-string"
        if isinstance(value, bool):
            val_type = "-bool"
            value = "true" if value else "false"
        elif isinstance(value, int):
            val_type = "-int"
        elif isinstance(value, float):
            val_type = "-float"
        
        cmd = ["defaults", "write", str(domain), str(key), val_type, str(value)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Failed to write default '{domain} {key}': {result.stderr.strip()}"
        return f"Successfully wrote '{value}' to '{domain} {key}'."

    def _reveal_pane(self, pane_id: str | None) -> str:
        if not pane_id:
            return "Error: 'pane_id' is required for 'reveal_pane'."
        script = f'tell application "System Settings" to reveal pane id "{pane_id}"'
        try:
            self._run_osascript(f'tell application "System Settings" to activate')
            self._run_osascript(script)
            return f"Revealed System Settings pane: {pane_id}"
        except Exception as e:
            return f"Failed to reveal pane: {str(e)}"

    def _run_shortcut(self, name: str | None) -> str:
        if not name:
            return "Error: Shortcut 'name' is required."
        cmd = ["shortcuts", "run", str(name)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return f"Failed to run shortcut '{name}': {result.stderr.strip()}"
        return f"Successfully ran shortcut '{name}'."

    def _get_detailed_power(self) -> str:
        try:
            result = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
            batt = result.stdout.strip()
            
            result_sys = subprocess.run(["pmset", "-g"], capture_output=True, text=True)
            sys_power = result_sys.stdout.strip()
            
            return f"Battery Status:\n{batt}\n\nSystem Power Settings:\n{sys_power}"
        except Exception as e:
            return f"Error getting power info: {str(e)}"
