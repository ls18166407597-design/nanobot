from nanobot.config.schema import Config


def test_web_proxy_fallback_to_telegram_proxy():
    config = Config()
    config.tools.web.proxy = None
    config.channels.telegram.proxy = "socks5://127.0.0.1:1080"
    web_proxy = config.tools.web.proxy or config.channels.telegram.proxy
    assert web_proxy == "socks5://127.0.0.1:1080"
