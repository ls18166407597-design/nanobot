import subprocess
from typing import Any

from nanobot.agent.tools.base import Tool


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
                ],
                "description": "The action to perform.",
            },
            "value": {
                "type": ["string", "integer"],
                "description": "Value for the action (e.g. volume level 0-100, app name).",
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
        }

    @property
    def confirm_mode(self) -> str:
        """Override base property to return instance value."""
        return self._confirm_mode

    async def execute(self, action: str, **kwargs: Any) -> str:
        value = kwargs.get("value")
        confirm = bool(kwargs.get("confirm"))
        warning = None

        if action in self._confirm_actions and not confirm:
            if self.confirm_mode == "require":
                return "Error: Confirmation required for disruptive macOS action. Please re-run with 'confirm': true in tool parameters."
            if self.confirm_mode == "warn":
                warning = "Warning: disruptive macOS action executed without 'confirm': true. This can be strictly required by setting tools.mac.confirm_mode to 'require'."

        try:
            result = ""
            if action == "set_volume":
                if value is None:
                    return "Error: 'value' (0-100) is required for 'set_volume'."
                result = self._set_volume(int(value))
            elif action == "get_volume":
                result = self._get_volume()
            elif action == "mute":
                result = self._set_mute(True)
            elif action == "unmute":
                result = self._set_mute(False)
            elif action == "open_app":
                if not value:
                    return "Error: App name is required for 'open_app'."
                result = self._open_app(str(value))
            elif action == "close_app":
                if not value:
                    return "Error: App name is required for 'close_app'."
                result = self._close_app(str(value))
            elif action == "list_apps":
                result = self._list_apps()
            elif action == "get_frontmost_app":
                result = self.get_frontmost_app_info()
            elif action == "activate_app":
                if not value:
                    return "Error: App name is required for 'activate_app'."
                result = self._activate_app(str(value))
            elif action == "battery":
                result = self._get_battery()
            elif action == "system_stats":
                result = self._get_system_stats()
            else:
                result = f"Unknown action: {action}"

            if warning:
                return f"{warning}\n{result}"
            return result
        except Exception as e:
            return f"Mac Tool Error: {str(e)}"

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
        script = 'tell application "System Events" to get name of (processes where background only is false)'
        apps = self._run_osascript(script)
        # AppleScript returns comma separated list
        return f"Running Apps: {apps}"

    def get_frontmost_app_info(self) -> str:
        """Get the name and bundle identifier of the frontmost application."""
        # Get name and bundle identifier using a more robust method
        script = 'set frontAppName to name of (info for (path to frontmost application))\n' \
                 'set frontAppID to id of application (frontAppName)\n' \
                 'get {frontAppName, frontAppID}'
        try:
            raw_output = self._run_osascript(script)
            # Robust split and strip
            results = [r.strip().strip('"').strip("'") for r in raw_output.replace(", ", ",").split(",")]
            name = results[0]
            bundle_id = results[1] if len(results) > 1 else "Unknown"

            app_info = f"App: {name} | ID: {bundle_id}"
            
            # Use system logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Frontmost App raw data: {app_info}")
                
            return app_info
        except Exception as e:
            # Fallback for restricted environments
            try:
                name = self._run_osascript('name of (info for (path to frontmost application))')
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
