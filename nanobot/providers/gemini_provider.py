"""Native Gemini provider implementation using Google Generative AI SDK."""

import json
import os
from typing import Any, List, Dict, Optional
from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class GeminiProvider(LLMProvider):
    """
    LLM provider using Google's native Generative AI SDK.
    
    This provider bypasses OpenAI-compatible proxies for better stability,
    native tool calling support, and direct multi-modal capabilities.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "gemini-1.5-flash",
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self._genai = None
        
        # Configure the SDK lazily to avoid import warnings when unused.
        self._configure_sdk(api_key=api_key, api_base=api_base)

    def _configure_sdk(self, api_key: str | None, api_base: str | None) -> None:
        genai = self._get_genai()

        config_kwargs = {
            "api_key": api_key or os.environ.get("GEMINI_API_KEY"),
            "transport": "rest",
        }

        if api_base:
            # The native SDK manages versioning internally. If api_base has /v1 or /v1beta, strip it.
            endpoint = api_base.rstrip("/")
            if endpoint.endswith("/v1"):
                endpoint = endpoint[:-3]
            elif endpoint.endswith("/v1beta"):
                endpoint = endpoint[:-7]
            config_kwargs["client_options"] = {"api_endpoint": endpoint}

        genai.configure(**config_kwargs)

    def _get_genai(self):
        if self._genai is not None:
            return self._genai
        try:
            import google.generativeai as genai  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "google.generativeai is required for GeminiProvider but is not installed."
            ) from e
        self._genai = genai
        return genai

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """
        Send a chat completion request via the native Gemini SDK.
        """
        run_model = model or self.default_model
        # Strip provider prefix if present (e.g. "gemini/gemini-1.5-flash")
        if "/" in run_model:
            run_model = run_model.split("/")[-1]

        # 1. Prepare Tools (Tools need to be part of the GenerativeModel init)
        genai_tools = None
        if tools:
            genai_tools = self._convert_tools(tools)

        # 2. Convert Messages to Gemini format
        system_instruction = None
        gemini_history = []
        
        i = 0
        while i < len(messages):
            msg = messages[i]
            role = msg.get("role")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = content
                i += 1
            elif role == "user":
                gemini_history.append({"role": "user", "parts": [content]})
                i += 1
            elif role == "assistant":
                parts = []
                if content:
                    parts.append(content)
                
                # Handle tool calls in history
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        # Extract tool call from OpenAI-style dict
                        func = tc.get("function", {})
                        args = json.loads(func.get("arguments", "{}")) if isinstance(func.get("arguments"), str) else func.get("arguments")
                        parts.append({
                            "function_call": {
                                "name": func.get("name"),
                                "args": args
                            }
                        })
                gemini_history.append({"role": "model", "parts": parts})
                i += 1
            elif role == "tool":
                # Collect all consecutive tool messages and format as a single user message
                # The local proxy may not support 'function' role, so we use 'user' instead
                tool_results = []
                while i < len(messages) and messages[i].get("role") == "tool":
                    tool_msg = messages[i]
                    tool_name = tool_msg.get("name", "unknown")
                    tool_content = tool_msg.get("content", "")
                    tool_results.append(f"[{tool_name}]: {tool_content}")
                    i += 1
                
                # Combine all tool results into a single user message
                combined_result = "\n\n".join(tool_results)
                gemini_history.append({
                    "role": "user",
                    "parts": [f"Tool execution results:\n{combined_result}"]
                })
            else:
                i += 1

        # 3. Last message must be from user in Gemini native SDK
        # In Nanobot, the current message is already the last one in 'messages' 
        # but it might have been converted to history.
        # We need to pop the last user message to use as the prompt.
        if gemini_history and gemini_history[-1]["role"] == "user":
            last_msg = gemini_history.pop()
            prompt = last_msg["parts"]
        else:
            prompt = "Continue" # Fallback

        # 4. Initialize Model
        genai = self._get_genai()
        model_instance = genai.GenerativeModel(
            model_name=run_model,
            tools=genai_tools,
            system_instruction=system_instruction
        )

        try:
            # 5. Call Model
            generation_config = genai.GenerationConfig(
                candidate_count=1,
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            
            # Use generate_content instead of start_chat for stateless direct matching of Nanobot's history
            request_contents = gemini_history + [{"role": "user", "parts": prompt}]
            logger.debug(f"Gemini Request Contents: {json.dumps(request_contents, indent=2, default=str)}")
            
            response = model_instance.generate_content(
                contents=request_contents,
                generation_config=generation_config,
                request_options={"timeout": timeout}
            )

            return self._parse_response(response)

        except Exception as e:
            logger.error(f"GeminiProvider error: {e}")
            return LLMResponse(
                content=f"Error calling native Gemini SDK: {str(e)}",
                finish_reason="error",
            )

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[Any]:
        """Convert OpenAI-style tool definitions to Gemini FunctionDeclarations."""
        declarations = []
        for t in tools:
            if t.get("type") != "function":
                continue
            
            func = t["function"]
            # Deep copy and clean the schema to avoid SDK crashes on 'type': ['string', 'null']
            cleaned_params = self._clean_schema(json.loads(json.dumps(func.get("parameters", {}))))
            
            declarations.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "parameters": cleaned_params
            })
        
        logger.debug(f"Gemini Tool Declarations: {json.dumps(declarations, indent=2, default=str)}")
        return [{"function_declarations": declarations}]

    def _clean_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Recursively clean JSON schema for Gemini SDK compatibility."""
        if not isinstance(schema, dict):
            return schema

        # Handle 'type' as a list (e.g., ['string', 'null'])
        if "type" in schema:
            t = schema["type"]
            if isinstance(t, list):
                # Pick the first non-null type
                non_null = [item for item in t if item != "null"]
                schema["type"] = non_null[0] if non_null else "string"
        
        # Remove unsupported fields
        schema.pop("default", None)
        schema.pop("title", None)
        
        # Recurse into properties
        if "properties" in schema and isinstance(schema["properties"], dict):
            for k, v in schema["properties"].items():
                schema["properties"][k] = self._clean_schema(v)
        
        # Recurse into items for arrays
        if "items" in schema and isinstance(schema["items"], dict):
            schema["items"] = self._clean_schema(schema["items"])

        return schema

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Gemini response info LLMResponse."""
        content = ""
        tool_calls = []
        
        # Check candidates
        if not response.candidates:
            return LLMResponse(content="No response candidates from Gemini.", finish_reason="stop")
            
        candidate = response.candidates[0]
        
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if part.text:
                    content += part.text
                if part.function_call:
                    # Map to our standard ToolCallRequest
                    tool_calls.append(ToolCallRequest(
                        id=f"call_{part.function_call.name[:8]}", # Gemini doesn't always provide IDs, generate one
                        name=part.function_call.name,
                        arguments=dict(part.function_call.args)
                    ))

        return LLMResponse(
            content=content.strip() or None,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count,
            } if hasattr(response, "usage_metadata") else {}
        )

    def get_default_model(self) -> str:
        return self.default_model
