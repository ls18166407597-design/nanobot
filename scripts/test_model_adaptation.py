
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path("/Users/liusong/Downloads/nanobot").resolve()))

from nanobot.providers.adapters import ModelAdapter
from nanobot.agent.context import ContextBuilder

def test_adapter():
    print("Testing ModelAdapter...")
    # Test 1: Identify reasoning models
    assert ModelAdapter.is_reasoning_model("deepseek-r1") == True
    assert ModelAdapter.is_reasoning_model("gpt-4o") == False
    assert ModelAdapter.is_reasoning_model("gemini-2.0-flash-thinking-exp-01-21") == True
    print("  Detection tests passed")

    # Test 2: Suggested params
    params_r1 = ModelAdapter.get_suggested_params("deepseek-r1")
    assert params_r1.get("temperature") == 0.6
    print("  Param suggestion tests passed")

def test_context_suppression():
    print("\nTesting ContextBuilder suppression...")
    workspace = Path("/Users/liusong/Downloads/nanobot/workspace")
    
    # Context with normal model
    ctx_normal = ContextBuilder(workspace, model="gpt-4o")
    prompt_normal = ctx_normal._get_reasoning_prompt()
    assert "Reasoning Format" in prompt_normal
    print("  Normal model included reasoning prompt")

    # Context with reasoning model
    ctx_r1 = ContextBuilder(workspace, model="deepseek-r1")
    prompt_r1 = ctx_r1._get_reasoning_prompt()
    assert prompt_r1 == ""
    print("  Reasoning model suppressed reasoning prompt")

if __name__ == "__main__":
    try:
        test_adapter()
        test_context_suppression()
        print("\nAll Phase 33 internal tests passed!")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        # sys.exit(1)
