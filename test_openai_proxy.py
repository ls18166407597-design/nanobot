import asyncio
import httpx
from openai import AsyncOpenAI

async def test():
    http_client = httpx.AsyncClient(trust_env=True)
    client = AsyncOpenAI(
        api_key="sk-xvgndcbfouwfcigmrbczzegyrsbkutwqcrprotvecerzrnxx",
        base_url="https://api.siliconflow.cn/v1",
        http_client=http_client
    )
    try:
        print("Testing SiliconFlow with proxy...")
        response = await client.chat.completions.create(
            model="Qwen/Qwen3-8B",
            messages=[{"role": "user", "content": "hello"}],
            timeout=30.0
        )
        print("Success!")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Failed: {e}")
    finally:
        await http_client.aclose()

if __name__ == "__main__":
    asyncio.run(test())
