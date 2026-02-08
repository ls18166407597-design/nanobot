
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import BrainConfig, AgentDefaults, AgentsConfig
from nanobot.providers.base import LLMProvider, LLMResponse

class MockProvider(LLMProvider):
    def get_default_model(self) -> str:
        return "mock-model"
        
    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, timeout=60.0) -> LLMResponse:
        print(f"DEBUG: MockProvider.chat called with max_tokens={max_tokens} (type: {type(max_tokens)})")
        if hasattr(max_tokens, 'max_tokens'):
            print("ERROR: max_tokens is a BrainConfig object!")
        return LLMResponse(content="Mock response")

async def main():
    print("Testing AgentLoop instantiation...")
    
    bus = MessageBus()
    provider = MockProvider()
    workspace = Path(".")
    
    # Brain config without max_tokens
    brain_config = BrainConfig()
    if hasattr(brain_config, "max_tokens"):
        print("WARNING: BrainConfig HAS max_tokens attribute (unexpected)")
    else:
        print("BrainConfig correctly has NO max_tokens attribute")

    try:
        # Simulate gateway instantiation
        agent = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=workspace,
            model="mock",
            brain_config=brain_config,
            # We explicitly pass max_tokens as we did in the fix
            max_tokens=9999
        )
        print(f"AgentLoop instantiated. self.max_tokens = {agent.max_tokens}")
        
        # Trigger _chat_with_failover via private method call (simulating loop)
        # We need to mock the context and sessions slightly or we can just call _chat_with_failover directly
        # if we set up enough state.
        
        print("Calling _chat_with_failover...")
        response = await agent._chat_with_failover(
            messages=[{"role": "user", "content": "hi"}],
            tools=[]
        )
        print(f"Response: {response.content}")
        print("SUCCESS: No error raised.")

    except Exception as e:
        print(f"FAILURE: Caught exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
