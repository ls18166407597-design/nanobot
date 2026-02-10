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


class ImessageConfig(BaseModel):
    """iMessage channel configuration using local imsg CLI."""

    enabled: bool = False
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers or emails


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""

    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    imessage: ImessageConfig = Field(default_factory=ImessageConfig)


class AgentDefaults(BaseModel):
    """Default agent configuration."""

    workspace: str = "./workspace"
    model: str = "gemini-3-flash"
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


class WebToolsConfig(BaseModel):
    """Web tools configuration."""

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
    error_fallback_channel: str = "cli"  # Fallback channel when system message has no origin
    error_fallback_chat_id: str = "direct"  # Fallback chat_id when system message has no origin
    busy_notice_threshold: int = 1  # Minimum queued/active tasks before showing busy notice
    busy_notice_debounce_seconds: int = 60  # Debounce seconds for busy notice
    enabled_tools: list[str] | None = None  # If set, only tools in this list will be registered
    disabled_tools: list[str] = Field(default_factory=list)  # Tools to skip during registration


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
        
        # 1. Match by model name to specific provider
        if "anthropic" in model_name_lower or "claude" in model_name_lower:
            return {"key": self.providers.anthropic.api_key, "path": "providers.anthropic.api_key"}
        if "deepseek" in model_name_lower:
            return {"key": self.providers.deepseek.api_key, "path": "providers.deepseek.api_key"}
        if "gemini" in model_name_lower:
            # If the user has an openai-compatible gemini key (like the proxy), prefer that
            if self.providers.openai.api_key and "127.0.0.1" in (self.providers.openai.api_base or ""):
                 return {"key": self.providers.openai.api_key, "path": "providers.openai.api_key"}
            return {"key": self.providers.gemini.api_key, "path": "providers.gemini.api_key"}
        if "gpt" in model_name_lower:
            return {"key": self.providers.openai.api_key, "path": "providers.openai.api_key"}
        if "qwen" in model_name_lower or "dashscope" in model_name_lower:
            return {"key": self.providers.dashscope.api_key, "path": "providers.dashscope.api_key"}
        if "zhipu" in model_name_lower or "glm" in model_name_lower:
            return {"key": self.providers.zhipu.api_key, "path": "providers.zhipu.api_key"}
        if "groq" in model_name_lower:
            return {"key": self.providers.groq.api_key, "path": "providers.groq.api_key"}
        if "moonshot" in model_name_lower or "kimi" in model_name_lower:
            return {"key": self.providers.moonshot.api_key, "path": "providers.moonshot.api_key"}

        # 2. Fallback: Check if openai provider has a key (catch-all for many compatibles)
        if self.providers.openai.api_key:
            return {"key": self.providers.openai.api_key, "path": "providers.openai.api_key"}

        return {"key": None, "path": "providers.openai.api_key"}

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
        if "anthropic" in model_name_lower or "claude" in model_name_lower:
            return self.providers.anthropic.api_base
        if "deepseek" in model_name_lower:
            return self.providers.deepseek.api_base
        if "gemini" in model_name_lower:
            # If it's gemini and we find a local proxy in openai section, use that
            if self.providers.openai.api_key and "127.0.0.1" in (self.providers.openai.api_base or ""):
                return self.providers.openai.api_base
            return self.providers.gemini.api_base
        if "gpt" in model_name_lower:
            return self.providers.openai.api_base
        if "qwen" in model_name_lower or "dashscope" in model_name_lower:
            return self.providers.dashscope.api_base
        if any(k in model_name_lower for k in ("zhipu", "glm", "zai")):
            return self.providers.zhipu.api_base
        if "moonshot" in model_name_lower or "kimi" in model_name_lower:
            return self.providers.moonshot.api_base
        
        # FINAL FALLBACK: Only use openai.api_base if it looks like a local proxy 
        # or if no other model match was found. DO NOT blindly fall back to vLLM.
        if self.providers.openai.api_base:
            return self.providers.openai.api_base
            
        return None

    model_config = SettingsConfigDict(
        env_prefix="NANOBOT_",
        env_nested_delimiter="__",
    )
