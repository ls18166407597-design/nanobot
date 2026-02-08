import asyncio
import os
import json
import time
from pathlib import Path

async def check_filesystem():
    """Verify filesystem tool capability."""
    print("🔍 Checking Filesystem...")
    test_file = Path("workspace/health_check_test.txt")
    try:
        test_file.write_text("health check")
        if test_file.read_text() == "health check":
            test_file.unlink()
            print("✅ Filesystem: OK")
            return True
        else:
            raise ValueError("Content mismatch")
    except Exception as e:
        print(f"❌ Filesystem: FAILED ({e})")
        return False

async def check_shell():
    """Verify shell execution."""
    print("🔍 Checking Shell...")
    try:
        proc = await asyncio.create_subprocess_shell(
            "uname -a",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            print(f"✅ Shell: OK ({stdout.decode().strip()[:30]}...)")
            return True
        else:
            raise ValueError(stderr.decode())
    except Exception as e:
        print(f"❌ Shell: FAILED ({e})")
        return False

async def check_vision():
    """Verify macOS Vision dependencies."""
    print("🔍 Checking Vision Frameworks...")
    try:
        import Vision
        import Quartz
        print("✅ Vision Frameworks: OK")
        return True
    except ImportError as e:
        print(f"❌ Vision Frameworks: MISSING ({e})")
        return False

async def run_diagnostics():
    """Run all health checks."""
    print("🚀 Starting Nanobot System Health Check...")
    print("-" * 40)
    
    results = {
        "filesystem": await check_filesystem(),
        "shell": await check_shell(),
        "vision": await check_vision(),
    }
    
    print("-" * 40)
    success = all(results.values())
    if success:
        print("🌟 SYSTEM HEALTHY")
    else:
        print("⚠️ SYSTEM ISSUES DETECTED")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
