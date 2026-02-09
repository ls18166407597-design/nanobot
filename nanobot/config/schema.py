"""Configuration schema using Pydantic."""

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WhatsAppConfig(BaseModel):
    """WhatsApp channel configuration."""

    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames
    proxy: str | None = (
        None  # HTTP/SOCKS5 proxy URL, e.g. "http://127.0.0.1:7890" or "socks5://127.0.0.1:1080"
    )


class FeishuConfig(BaseModel):
    """Feishu/Lark channel configuration using WebSocket long connection."""

    enabled: bool = False
    app_id: str = ""  # App ID from Feishu Open Platform
    app_secret: str = ""  # App Secret from Feishu Open Platform
    encrypt_key: str = ""  # Encrypt Key for event subscription (optional)
    verification_token: str = ""  # Verification Token for event subscription (optional)
    allow_from: list[str] = Field(default_factory=list)  # Allowed user open_ids


class DiscordConfig(BaseModel):
    """Discord channel configuration."""

    enabled: bool = False
    token: str = ""  # Bot token from Discord Developer Portal
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs
    gateway_url: str = "wss://gateway.discord.gg/?v=10&encoding=json"
    intents: int = 37377  # GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""

    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration."""

    workspace: str = "./workspace"
    model: str = "Qwen/Qwen2.5-7B-Instruct"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20


class AgentsConfig(BaseModel):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""

    api_key: str = ""
    api_base: str | None = None


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""

    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)  # 阿里云通义千问
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""

    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""

    api_key: str = ""  # Brave Search API key
    max_results: int = 5


class WebToolsConfig(BaseModel):
    """Web tools configuration."""

    search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    proxy: str | None = None  # Proxy for browser tool


class ExecToolConfig(BaseModel):
    """Shell exec tool configuration."""

    timeout: int = 60


class MacToolsConfig(BaseModel):
    """macOS tools configuration."""

    # off: no prompt, warn: allow but warn when confirm missing, require: block without confirm
    confirm_mode: str = "warn"


class ToolsConfig(BaseModel):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    mac: MacToolsConfig = Field(default_factory=MacToolsConfig)
    restrict_to_workspace: bool = False  # If true, restrict all tool access to workspace directory


class BrainConfig(BaseModel):
    """Configuration for AI cognitive features."""
    
    auto_summarize: bool = True
    light_rag: bool = True
    safety_guard: bool = True
    reasoning: bool = True  # Toggle for reasoning instructions (<think> format)
    
    # Heartbeat settings
    heartbeat_enabled: bool = False  # Disabled by default to save costs
    heartbeat_interval: int = 1800  # Default 30 minutes in seconds
    
    # Advanced settings
    memory_chunk_size: int = 500
    summary_threshold: int = 40  # Messages count to trigger summary
    
    # Registry for additional providers (e.g. One API)
    provider_registry: list[dict[str, str]] = Field(default_factory=list)


class Config(BaseSettings):
    """Root configuration for nanobot."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    brain: BrainConfig = Field(default_factory=BrainConfig)

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()




    def get_api_key_info(self, model: str | None = None) -> dict[str, str | None]:
        """Get API key and its source information (JSON path)."""
        model_name = (model or self.agents.defaults.model)
        
        # 0. High priority: Check brain.provider_registry
        if hasattr(self, "brain") and self.brain.provider_registry:
            for p in self.brain.provider_registry:
                # Support both exact match and case-insensitive match for registry
                if (
                    p.get("name") == model_name or 
                    p.get("model") == model_name or 
                    p.get("model", "").lower() == model_name.lower()
                ):
                    api_key = p.get("api_key") or p.get("apiKey")
                    if api_key:
                        return {
                            "key": api_key, 
                            "path": f"brain.providerRegistry[{p.get('name')}]",
                            "model": p.get("model")
                        }

        model_name_lower = model_name.lower()
        
        # Map of keywords to (path, provider_config)
        providers_map = {
            "openrouter": ("providers.openrouter.api_key", self.providers.openrouter),
            "deepseek": ("providers.deepseek.api_key", self.providers.deepseek),
            "anthropic": ("providers.anthropic.api_key", self.providers.anthropic),
            "claude": ("providers.anthropic.api_key", self.providers.anthropic),
            "openai": ("providers.openai.api_key", self.providers.openai),
            "gpt": ("providers.openai.api_key", self.providers.openai),
            "gemini": ("providers.gemini.api_key", self.providers.gemini),
            "zhipu": ("providers.zhipu.api_key", self.providers.zhipu),
            "glm": ("providers.zhipu.api_key", self.providers.zhipu),
            "zai": ("providers.zhipu.api_key", self.providers.zhipu),
            "dashscope": ("providers.dashscope.api_key", self.providers.dashscope),
            "qwen": ("providers.dashscope.api_key", self.providers.dashscope),
            "groq": ("providers.groq.api_key", self.providers.groq),
            "moonshot": ("providers.moonshot.api_key", self.providers.moonshot),
            "kimi": ("providers.moonshot.api_key", self.providers.moonshot),
            "vllm": ("providers.vllm.api_key", self.providers.vllm),
        }
        
        # 1. Match by model name
        for keyword, (path, provider) in providers_map.items():
            if keyword in model_name_lower and provider.api_key:
                return {"key": provider.api_key, "path": path}
                
        # 2. Fallback: first available
        fallback_order = [
            "openrouter", "deepseek", "anthropic", "openai", 
            "gemini", "zhipu", "dashscope", "moonshot", "vllm", "groq"
        ]
        for name in fallback_order:
            path, provider = providers_map[name]
            if provider.api_key:
                return {"key": provider.api_key, "path": path}
        
        # 3. Not found: return expected path for this model if possible
        expected_path = "providers.openrouter.api_key"
        for keyword, (path, _) in providers_map.items():
            if keyword in model_name:
                expected_path = path
                break
                
        return {"key": None, "path": expected_path}

    def get_api_key(self, model: str | None = None) -> str | None:
        """Get API key for the given model (or default model)."""
        return self.get_api_key_info(model)["key"]

    def get_api_base(self, model: str | None = None) -> str | None:
        """Get API base URL based on model name."""
        model_name = (model or self.agents.defaults.model)
        
        # 0. High priority: Check brain.provider_registry
        if hasattr(self, "brain") and self.brain.provider_registry:
            for p in self.brain.provider_registry:
                if (
                    p.get("name") == model_name or 
                    p.get("model") == model_name or 
                    p.get("model", "").lower() == model_name.lower()
                ):
                    base_url = p.get("base_url") or p.get("baseUrl")
                    if base_url:
                        return base_url

        model_name_lower = model_name.lower()
        if "openrouter" in model_name_lower:
            return self.providers.openrouter.api_base or "https://openrouter.ai/api/v1"
        if any(k in model_name_lower for k in ("zhipu", "glm", "zai")):
            return self.providers.zhipu.api_base
        if "vllm" in model_name_lower:
            return self.providers.vllm.api_base
        # Fallback to vLLM/Local if configured (allows using any model name with local proxy)
        if self.providers.vllm.api_base:
            return self.providers.vllm.api_base
        return None

    model_config = SettingsConfigDict(
        env_prefix="NANOBOT_",
        env_nested_delimiter="__",
    )
