
import asyncio
import os
import time
import json
from loguru import logger
from nanobot.providers.openai_provider import OpenAIProvider

# Helper to load config
def load_config():
    from nanobot.config.loader import get_config_path
    config_path = get_config_path()
    with open(config_path, "r") as f:
        return json.load(f)

async def test_provider(name, config, prompt, timeout=60.0):
    logger.info(f"Testing provider: {name} (Model: {config['model']})")
    
    provider = OpenAIProvider(
        api_key=config['api_key'],
        api_base=config['base_url'],
        default_model=config['model']
    )
    
    start_time = time.time()
    try:
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout
        )
        duration = time.time() - start_time
        
        if response.finish_reason == "error":
            logger.error(f"❌ {name} Failed: {response.content} (Time: {duration:.2f}s)")
            return False, duration, response.content
        else:
            logger.info(f"✅ {name} Success! (Time: {duration:.2f}s, Len: {len(response.content)})")
            return True, duration, None
            
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ {name} Exception: {e} (Time: {duration:.2f}s)")
        return False, duration, str(e)

async def main():
    config = load_config()
    registry = config.get("brain", {}).get("providerRegistry", [])
    
    # Filter for SiliconFlow providers (exclude local)
    targets = [p for p in registry if "siliconflow" in p.get("base_url", "")]
    
    if not targets:
        logger.error("No SiliconFlow providers found in config!")
        return

    logger.info(f"Found {len(targets)} SiliconFlow providers to test.")

    # Test 1: Simple Connectivity (Ping)
    logger.info("\n=== Test 1: Simple Connectivity (Ping) ===")
    for p in targets:
        await test_provider(p["name"], p, "Hello, are you online?", timeout=10.0)

    # Test 2: Simulated 'Work' (Long Context + Long Output)
    logger.info("\n=== Test 2: Stress Test (Long Context + Reasoning) ===")
    long_prompt = "You are a data analyst. " + ("Here is some random log data: [INFO] process started... " * 100) + "\nPlease analyze the logs and write a summary report."
    
    for p in targets:
        logger.info(f"Sending heavy load to {p['name']}...")
        await test_provider(p["name"], p, long_prompt, timeout=30.0)

if __name__ == "__main__":
    asyncio.run(main())
