import asyncio
import time
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from nanobot.process import CommandQueue, CommandLane
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | {message}")

async def task(name, duration):
    logger.info(f"START {name}")
    await asyncio.sleep(duration)
    logger.info(f"END   {name}")
    return name

async def run_verification():
    logger.info("Starting CommandQueue Verification")
    
    # 1. Enqueue 3 tasks in MAIN (should be serial)
    logger.info("Enqueuing 3 tasks to MAIN (1s each)")
    t0 = time.time()
    
    f1 = await CommandQueue.enqueue(CommandLane.MAIN, lambda: task("MAIN_1", 1.0))
    f2 = await CommandQueue.enqueue(CommandLane.MAIN, lambda: task("MAIN_2", 1.0))
    f3 = await CommandQueue.enqueue(CommandLane.MAIN, lambda: task("MAIN_3", 1.0))
    
    # 2. Enqueue 1 task in BACKGROUND (should be parallel)
    # Note: enqueue waits for the *future* (result), not the start of execution.
    # Wait, CommandQueue.enqueue returns the *result* if awaited?
    # No, my implementation returns `await future`.
    # So if I await the enqueue call, I verify serial execution *of the enqueue call*?
    # No, enqueue checks drain. But if I await the result inside enqueue, I block until it's done.
    
    # Wait, my `enqueue` implementation: `return await future`.
    # This means `enqueue` blocks the caller until the task is DONE.
    # IF I call it sequentially in `run_verification`, I am serializing it myself!
    
    # Correct usage for parallelism: use asyncio.gather or create_task wrapping the enqueue call.
    
    pass

async def run_parallel_enqueue():
    # We need to simulate the AgentLoop which calls `asyncio.create_task(wrapper(msg))`
    # The wrapper internally awaits enqueue.
    
    async def enqueue_wrapper(lane, name, duration):
        await CommandQueue.enqueue(lane, lambda: task(name, duration))

    logger.info("Spawning 3 MAIN tasks + 1 BACKGROUND task concurrently...")
    
    start_time = time.time()
    
    # Spawn them "at the same time"
    tasks = [
        asyncio.create_task(enqueue_wrapper(CommandLane.MAIN, "MAIN_1", 1.0)),
        asyncio.create_task(enqueue_wrapper(CommandLane.MAIN, "MAIN_2", 1.0)),
        asyncio.create_task(enqueue_wrapper(CommandLane.MAIN, "MAIN_3", 1.0)),
        asyncio.create_task(enqueue_wrapper(CommandLane.BACKGROUND, "BG_1", 2.0)),
    ]
    
    await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    logger.info(f"Total time: {total_time:.2f}s")
    
    if 2.9 < total_time < 3.2:
        logger.info("✅ PASS: MAIN tasks ran serially (~3s total)")
    else:
        logger.error(f"❌ FAIL: Expected ~3s, got {total_time:.2f}s")

    # To verify BG ran in parallel, we need to check logs/timing.
    # BG_1 (2s) should finish BEFORE MAIN_3 (starts at 2s, ends at 3s).
    
if __name__ == "__main__":
    asyncio.run(run_parallel_enqueue())
