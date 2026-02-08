import asyncio
import os
import json
import socket
import sys
from pathlib import Path

class NanoAudit:
    def __init__(self):
        self.results = {}
        self.report_path = Path("audit_report.json")

    async def audit_connectivity(self):
        """Check internet and proxy connectivity."""
        print("🌐 Auditing Connectivity...")
        try:
            # Check local gateway port (default 8000)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                gateway_ok = s.connect_ex(('127.0.0.1', 8000)) == 0
            
            # Check external connectivity (proxy test)
            proc = await asyncio.create_subprocess_shell(
                "curl -I -s --max-time 5 https://www.google.com",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            internet_ok = proc.returncode == 0
            
            gateway_live = gateway_ok
            internet_accessible = internet_ok
            
            self.results["connectivity"] = {
                "gateway_live": gateway_live,
                "internet_accessible": internet_accessible,
                "status": "PASS" if internet_accessible else "FAIL",
                "gateway_status": "PASS" if gateway_live else "WARN (Stopped)"
            }
        except Exception as e:
            self.results["connectivity"] = {"status": "FAIL", "error": str(e)}

    async def audit_tools(self):
        """Verify core tool availability and logic."""
        print("🛠️ Auditing Tools...")
        tools_status = {}
        
        # Filesystem
        try:
            test_path = Path("workspace/audit_tmp.txt")
            test_path.write_text("audit")
            if test_path.read_text() == "audit":
                test_path.unlink()
                tools_status["filesystem"] = "PASS"
            else:
                tools_status["filesystem"] = "FAIL (Read mismatch)"
        except Exception as e:
            tools_status["filesystem"] = f"FAIL ({e})"

        # Vision
        try:
            import Vision
            import Quartz
            tools_status["vision"] = "PASS"
        except ImportError:
            tools_status["vision"] = "FAIL (Missing pyobjc-framework-Vision/Quartz)"

        tools_status["status"] = "PASS" if all(v == "PASS" for v in tools_status.values()) else "FAIL"
        self.results["tools"] = tools_status

    async def audit_environment(self):
        """Verify localized environment settings."""
        print("🏠 Auditing Environment...")
        self.results["environment"] = {
            "NANOBOT_HOME": os.getenv("NANOBOT_HOME", "UNSET"),
            "local_config_exists": Path(".home/config.json").exists() or Path(".nanobot/config.json").exists(),
            "local_workspace_exists": Path("workspace").exists(),
            "status": "PASS" if Path("workspace").exists() else "FAIL"
        }

    def save_report(self):
        with open(self.report_path, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📊 Audit Report saved to {self.report_path}")

    async def run(self):
        print("🚀 Starting AI Health Audit Regression Suite...")
        await self.audit_connectivity()
        await self.audit_tools()
        await self.audit_environment()
        self.save_report()
        
        # Summary for STDOUT
        ignored_keys = ["connectivity"] # Connectivity has its own sub-status
        core_healthy = all(v.get("status") == "PASS" for k, v in self.results.items() if isinstance(v, dict))
        
        overall = "CLEAN" if core_healthy else "DEGRADED"
        print(f"\nAudit Conclusion: {overall}")
        return core_healthy

if __name__ == "__main__":
    audit = NanoAudit()
    success = asyncio.run(audit.run())
    sys.exit(0 if success else 1)
