import sys
import os
import asyncio
import time

# Add project root to path
sys.path.append(os.getcwd())

from nanobot.agent.models import ModelRegistry, ProviderInfo
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | {message}")

async def test_auth_rotation():
    logger.info("Starting Auth Rotation Verification")
    
    registry = ModelRegistry()
    
    # 1. Register Mock Providers
    # Note: register is async but here we can just manually populate for unit testing logic
    registry.providers["provider_A"] = ProviderInfo(
        name="provider_A", base_url="http://a", api_key="sk-a", models=["gpt-4"]
    )
    registry.providers["provider_B"] = ProviderInfo(
        name="provider_B", base_url="http://b", api_key="sk-b", models=["gpt-4"]
    )
    
    # 2. Check Active
    active = registry.get_active_providers(model="gpt-4")
    logger.info(f"Active count: {len(active)}")
    assert len(active) == 2
    logger.info("✅ Initial Active Check Passed")
    
    # 3. Report Failure for A (short cooldown)
    logger.info("Reporting failure for provider_A (cooldown 2s)")
    registry.report_failure("provider_A", duration=2.0)
    
    # 4. Check Active (should exclude A)
    active_after = registry.get_active_providers(model="gpt-4")
    logger.info(f"Active count after failure: {len(active_after)}")
    assert len(active_after) == 1
    assert active_after[0].name == "provider_B"
    logger.info("✅ Cooldown Exclusion Passed")
    
    # 5. Wait for Cooldown
    logger.info("Waiting 2.1s for cooldown...")
    await asyncio.sleep(2.1)
    
    # 6. Check Active (should include A again)
    active_final = registry.get_active_providers(model="gpt-4")
    logger.info(f"Active count final: {len(active_final)}")
    assert len(active_final) == 2
    logger.info("✅ Cooldown Expiration Passed")

if __name__ == "__main__":
    asyncio.run(test_auth_rotation())
