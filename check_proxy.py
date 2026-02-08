import asyncio
from nanobot.config.loader import load_config
from playwright.async_api import async_playwright

async def main():
    config = load_config()
    print(f"Tools Web Proxy: {config.tools.web.proxy}")
    
    async with async_playwright() as p:
        # Test without explicit proxy (should follow system/Shadowrocket)
        print("\nTesting JD.com without explicit proxy...")
        try:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            start = asyncio.get_event_loop().time()
            await page.goto("https://www.jd.com", timeout=10000)
            end = asyncio.get_event_loop().time()
            print(f"JD.com loaded in {end - start:.2f}s")
            await browser.close()
        except Exception as e:
            print(f"JD.com load failed: {e}")

        # Test with configured proxy if exists
        if config.tools.web.proxy:
            print(f"\nTesting JD.com with configured proxy: {config.tools.web.proxy}")
            try:
                browser = await p.chromium.launch(headless=True, proxy={"server": config.tools.web.proxy})
                page = await browser.new_page()
                start = asyncio.get_event_loop().time()
                await page.goto("https://www.jd.com", timeout=10000)
                end = asyncio.get_event_loop().time()
                print(f"JD.com loaded (with proxy) in {end - start:.2f}s")
                await browser.close()
            except Exception as e:
                print(f"JD.com (with proxy) load failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
