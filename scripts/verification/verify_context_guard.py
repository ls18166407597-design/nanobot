import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from nanobot.agent.context_guard import ContextGuard, TokenCounter
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | {message}")

def test_context_guard():
    logger.info("Starting ContextGuard Verification")
    
    # 1. Test TokenCounter
    text = "Hello world " * 10
    count = TokenCounter.count_text(text)
    logger.info(f"Text length: {len(text)}, Token count: {count}")
    
    # 2. Test ContextGuard Logic
    limit = 100
    guard = ContextGuard(limit=limit)
    logger.info(f"Guard limit: {limit}, Threshold: {guard.THRESHOLD} ({limit * guard.THRESHOLD})")
    
    # Case A: Below threshold
    msgs_safe = [{"role": "user", "content": "short message"}] # ~5 tokens
    res_safe = guard.evaluate(msgs_safe)
    logger.info(f"Case A Usage: {res_safe['usage']}")
    assert res_safe["is_safe"] == True
    assert res_safe["should_compact"] == False
    logger.info("✅ Case A (Safe) Passed")
    
    # Case B: Above threshold
    # Construct a long message
    long_text = "word " * 80 # ~80 tokens
    msgs_risky = [{"role": "user", "content": long_text}]
    res_risky = guard.evaluate(msgs_risky)
    logger.info(f"Case B Usage: {res_risky['usage']}")
    assert res_risky["is_safe"] == True # Still under limit (100)
    assert res_risky["should_compact"] == True # > 85
    logger.info("✅ Case B (Compact) Passed")
    
    # Case C: Over limit
    very_long_text = "word " * 150 # ~150 tokens
    msgs_over = [{"role": "user", "content": very_long_text}]
    res_over = guard.evaluate(msgs_over)
    logger.info(f"Case C Usage: {res_over['usage']}")
    assert res_over["is_safe"] == False
    logger.info("✅ Case C (Unsafe) Passed")

if __name__ == "__main__":
    test_context_guard()
