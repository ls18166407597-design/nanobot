"""Adapters for model-specific behavior and optimizations."""

from typing import Any, Dict, Optional, List


class ModelAdapter:
    """
    Centralized adapter for handling LLM model-specific quirks, 
    ideal parameters, and capability detection.
    """

    @staticmethod
    def is_reasoning_model(model: str) -> bool:
        """Check if the model has native reasoning (thinking) capabilities."""
        m = model.lower()
        return any(k in m for k in [
            "r1", 
            "thinking", 
            "reasoning",
            "o1",
            "o3"
        ])

    @staticmethod
    def get_suggested_params(model: str) -> Dict[str, Any]:
        """Get suggested parameters for a specific model."""
        m = model.lower()
        params = {}

        # 1. Temperature for reasoning models should be lower for stability
        if ModelAdapter.is_reasoning_model(model):
            # DeepSeek R1 and OpenAI O1 often prefer temperature 0 or 0.6
            params["temperature"] = 0.6 if "r1" in m else 1.0 
            
            # Kimi k2.5 only supports 1.0 (already handled in LiteLLMProvider, but keeping here)
            if "kimi" in m:
                params["temperature"] = 1.0

        # 2. Max tokens adjustments
        if "flash" in m:
            # Flash models often have smaller output limits or we want them faster
            pass

        return params

    @staticmethod
    def get_stop_sequences(model: str) -> Optional[List[str]]:
        """Get stop sequences for models that might leak internal chain-of-thought."""
        m = model.lower()
        # If we see common reasoning tags leaking, we can add them as stop sequences 
        # for non-reasoning providers that might be using them.
        return None

    @staticmethod
    def needs_reasoning_suppression(model: str) -> bool:
        """Check if we should suppress the reasoning system prompt instructions."""
        # If it's a native reasoning model, we don't need to tell it to use <think> tags
        # as it already does it (or uses a hidden state).
        return ModelAdapter.is_reasoning_model(model)
