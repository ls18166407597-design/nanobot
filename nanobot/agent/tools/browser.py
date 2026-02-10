"""Browser tools using Playwright for direct web interaction."""

import asyncio
import json
import os
from typing import Any, Literal
from loguru import logger

from nanobot.agent.tools.base import Tool

class BrowserTool(Tool):
    """
    Direct web browsing and searching using Playwright.
    No API keys required.
    """

    name = "browser"
    description = """
    A powerful browser tool to search and browse the web directly.
    Use this when you need to find real-time information or read detailed web content.
    
    Actions:
    - search: Search the web using a search engine (Bing).
    - browse: Open a specific URL and extract its readable content.
    - install: Install the necessary browser binaries (run this first if you get a Missing Browser error).
    """

    def __init__(self, proxy: str | None = None):
        super().__init__()
        self.proxy = proxy

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "browse", "install"],
                "description": "The action to perform"
            },
            "query": {
                "type": "string",
                "description": "The search query (required for search action)"
            },
            "engine": {
                "type": "string",
                "enum": ["bing", "google"],
                "description": "Search engine to use (default: bing). Bing is faster and more reliable. Google has strict bot detection and often fails.",
                "default": "bing"
            },
            "url": {
                "type": "string",
                "description": "The URL to browse (required for browse action)"
            },
            "wait_ms": {
                "type": "integer",
                "description": "Time to wait for page load in milliseconds (default: 2000)",
                "default": 2000
            }
        },
        "required": ["action"]
    }

    async def execute(self, action: str, **kwargs: Any) -> str:
        if action == "install":
            return await self._install_playwright()
        
        if action == "search":
            query = kwargs.get("query")
            engine = kwargs.get("engine", "bing")
            if not query:
                return "Error: 'query' is required for search action."
            return await self._search(query, engine, kwargs.get("wait_ms", 2000))
            
        if action == "browse":
            url = kwargs.get("url")
            if not url:
                return "Error: 'url' is required for browse action."
            return await self._browse(url, kwargs.get("wait_ms", 2000))

        return f"Error: Unknown action '{action}'."

    async def _install_playwright(self) -> str:
        """Install Playwright browser binaries."""
        import asyncio.subprocess
        try:
            logger.info("Installing Playwright browser binaries...")
            process = await asyncio.create_subprocess_exec(
                "python", "-m", "playwright", "install", "chromium",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode == 0:
                return "Playwright browsers installed successfully. 🐾 Boss, I'm ready to browse!"
            else:
                return f"Error installing Playwright: {stderr.decode()}"
        except Exception as e:
            return f"Error running install command: {str(e)}"

    async def _get_browser_config(self) -> dict[str, Any]:
        """Detect local browsers to avoid heavy downloads."""
        # Common macOS paths for Chrome, Edge, and Arc
        paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Arc.app/Contents/MacOS/Arc",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            os.path.expanduser("~/Applications/Arc.app/Contents/MacOS/Arc"),
        ]
        
        for path in paths:
            if os.path.exists(path):
                logger.debug(f"Found local browser at: {path}")
                return {"executable_path": path}
            
        return {} # Fallback to default Playwright chromium

    async def _search(self, query: str, engine: str, wait_ms: int) -> str:
        """Search using Bing or Google via Playwright (preferring local browser)."""
        from playwright.async_api import async_playwright
        
        config = await self._get_browser_config()
        try:
            async with async_playwright() as p:
                launch_args = {"headless": True, **config}
                
                # Smart Proxy: Only use proxy for search engines/international sites
                if self.proxy:
                    launch_args["proxy"] = {"server": self.proxy}
                
                browser = await p.chromium.launch(**launch_args)
                user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                
                # Extra headers to avoid bot detection
                extra_headers = {
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Sec-Ch-Ua": '"Not_A Brand";v="120", "Chromium";v="120", "Google Chrome";v="120"',
                }
                
                page = await browser.new_page(user_agent=user_agent, extra_http_headers=extra_headers)
                
                # Smart Routing: Add site: operator if specific keywords are found
                q_lower = query.lower()
                if "site:" not in q_lower:
                    site_mappings = {
                        "github": "github.com",
                        "reddit": "reddit.com",
                        "stackoverflow": "stackoverflow.com",
                        "zhihu": "zhihu.com",
                        "douban": "douban.com",
                        "v2ex": "v2ex.com"
                    }
                    for kw, domain in site_mappings.items():
                        if kw in q_lower:
                            query += f" site:{domain}"
                            break

                # Search URL and Selector based on engine
                if engine == "google":
                    search_url = f"https://www.google.com/search?q={query}"
                    result_selector = ".g, div.g, #search .g"
                else:
                    search_url = f"https://www.bing.com/search?q={query}"
                    result_selector = ".b_algo, #b_results .b_algo, li.b_algo, div.ans"

                logger.info(f"Searching ({engine}): {search_url}")
                
                await page.goto(search_url)
                
                # Wait for results to load
                try:
                    await page.wait_for_selector(result_selector, timeout=15000) # Reduce timeout for faster fallback
                except Exception:
                    logger.warning(f"Timeout waiting for search results on {engine}")
                    if engine == "google":
                        logger.info("Retrying with Bing for better reliability...")
                        await browser.close()
                        return await self._search(query, "bing", wait_ms)
                    # For Bing or second try, we continue and attempt fallback extraction
                
                # Extraction logic for both engines
                results = await page.evaluate(f'''(selector_str) => {{
                    const selectors = selector_str.split(", ");
                    let items = [];
                    let activeSelector = "";
                    for (const sel of selectors) {{
                        const found = document.querySelectorAll(sel);
                        if (found.length > 0) {{
                            items = Array.from(found);
                            activeSelector = sel;
                            break;
                        }}
                    }}

                    if (items.length === 0) {{
                        // Very broad fallback: look for any links that look like search results
                        const allLinks = Array.from(document.querySelectorAll("a[href^='http']"));
                        items = allLinks.filter(a => {{
                            const href = a.href;
                            // Exclude common search engine internal links
                            return !href.includes("google.com") && 
                                   !href.includes("bing.com") && 
                                   !href.includes("microsoft.com") && 
                                   !href.includes("javascript:") &&
                                   a.innerText.trim().length > 10;
                        }}).slice(0, 5).map(a => a.parentElement); 
                        if (items.length > 0) activeSelector = "fallback";
                    }}

                    return items.slice(0, 5).map(item => {{
                        let title = "No title";
                        let url = "No URL";
                        let snippet = "No description";

                        // Google Structure
                        if (activeSelector.includes(".g")) {{
                            const h3 = item.querySelector("h3");
                            const a = item.querySelector("a");
                            const s = item.querySelector(".VwiC3b") || item.querySelector(".IsZvec");
                            if (h3) title = h3.innerText.split("\\n")[0];
                            if (a) url = a.href;
                            if (s) snippet = s.innerText;
                        }} 
                        // Bing Structure or Fallback
                        else {{
                            const h2 = item.querySelector("h2") || item.querySelector("h3") || item;
                            const a = item.querySelector("a");
                            const s = item.querySelector(".b_caption p") || item.querySelector(".b_lineclamp2") || item.querySelector(".b_algo_snippet") || item;
                            if (h2) title = h2.innerText.split("\\n")[0];
                            if (a) url = a.href;
                            if (s && s !== item) snippet = s.innerText;
                        }}
                        return {{ title, url, snippet }};
                    }});
                }}''', result_selector)
                
                await browser.close()
                
                if not results:
                    return f"No results found for '{query}' on {engine}."
                
                output = [f"Search results for '{query}' ({engine}):\n"]
                for i, res in enumerate(results, 1):
                    # Filter out empty or garbage results
                    if res['url'].startswith("http"):
                        output.append(f"{i}. {res['title']}")
                        output.append(f"   URL: {res['url']}")
                        output.append(f"   {res['snippet']}\n")
                
                return "\n".join(output)
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                return "Error: Playwright browsers not installed. Please call the 'browser' tool with action='install' first."
            return f"Error during search: {str(e)}"
        return f"Error: Search failed for {query}"

    async def _browse(self, url: str, wait_ms: int) -> str:
        """Open a URL and extract content (preferring local browser)."""
        from playwright.async_api import async_playwright
        
        config = await self._get_browser_config()
        
        launch_args = {"headless": True, **config}
        if self.proxy:
            launch_args["proxy"] = {"server": self.proxy}

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(**launch_args)
                
                user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                page = await browser.new_page(user_agent=user_agent)
                
                logger.info(f"Browsing: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(wait_ms / 1000.0)
                
                title = await page.title()
                # Simple content extraction
                content = await page.evaluate('''() => {
                    // Try to find the article or main content
                    const main = document.querySelector('article') || document.querySelector('main') || document.body;
                    return main.innerText;
                }''')
                
                await browser.close()
                
                # Cleanup and limit content
                text = content.strip()
                if len(text) > 10000:
                    text = text[:10000] + "\n\n[Content truncated...]"
                
                return f"# {title}\n\nURL: {url}\n\n{text}"
        except Exception as e:
            if "Executable doesn't exist" in str(e):
                return "Error: Playwright browsers not installed. Please call the 'browser' tool with action='install' first."
            return f"Error during browsing: {str(e)}"
        return "Error: Unknown error during browsing."
