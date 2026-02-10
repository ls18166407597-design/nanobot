
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from nanobot.agent.tools.provider import ProviderTool
from nanobot.agent.models import ProviderInfo

@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.register = AsyncMock()
    return registry

@pytest.fixture
def provider_tool(mock_registry):
    return ProviderTool(registry=mock_registry)

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.brain.provider_registry = []
    return config

def test_provider_add(provider_tool, mock_registry, mock_config):
    # Mock successful check
    mock_registry.register.return_value = ProviderInfo(
        name="test_provider",
        base_url="http://test.com",
        api_key="sk-test",
        balance=10.0,
        models=["gpt-4"]
    )

    with patch("nanobot.agent.tools.provider.load_config", return_value=mock_config), \
         patch("nanobot.agent.tools.provider.save_config") as mock_save:
        
        async def run_test():
            return await provider_tool.execute(
                action="add",
                name="test_provider",
                base_url="http://test.com",
                api_key="sk-test"
            )
        
        result = asyncio.run(run_test())
        
        assert "Successfully Added provider 'test_provider'" in result.output
        assert len(mock_config.brain.provider_registry) == 1
        assert mock_config.brain.provider_registry[0]["name"] == "test_provider"
        mock_save.assert_called_once()

def test_provider_remove(provider_tool, mock_config):
    mock_config.brain.provider_registry = [
        {"name": "test_provider", "base_url": "http://test.com", "api_key": "sk-test"}
    ]

    with patch("nanobot.agent.tools.provider.load_config", return_value=mock_config), \
         patch("nanobot.agent.tools.provider.save_config") as mock_save:
        
        async def run_test():
            return await provider_tool.execute(action="remove", name="test_provider")
            
        result = asyncio.run(run_test())
        
        assert "Successfully removed provider 'test_provider'" in result.output
        assert len(mock_config.brain.provider_registry) == 0
        mock_save.assert_called_once()

def test_provider_list(provider_tool, mock_config):
    mock_config.brain.provider_registry = [
        {"name": "p1", "base_url": "u1", "api_key": "k1"},
        {"name": "p2", "base_url": "u2", "api_key": "k2"}
    ]

    with patch("nanobot.agent.tools.provider.load_config", return_value=mock_config):
        async def run_test():
            return await provider_tool.execute(action="list")
            
        result = asyncio.run(run_test())
        
        assert "p1 (u1)" in result.output
        assert "p2 (u2)" in result.output
