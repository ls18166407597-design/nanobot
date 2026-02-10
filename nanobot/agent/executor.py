import hashlib
import json
import time
import traceback
from typing import Any, Dict, Set, Protocol
from loguru import logger

from nanobot.agent.tools.base import Tool, ToolResult

class ToolRegistryProtocol(Protocol):
    def get(self, name: str) -> Tool | None:
        ...
    async def execute(self, name: str, params: dict[str, Any]) -> "ToolResult":
        ...

class ToolExecutor:
    """
    Manages tool execution with loop prevention and AI-friendly feedback.
    """
    def __init__(
        self,
        registry: ToolRegistryProtocol,
        max_failed_history: int = 100,
        failed_ttl_seconds: int = 600,
    ):
        self.registry = registry
        self.failed_call_hashes: Set[str] = set()
        self._failed_order: list[str] = []
        self.max_failed_history = max_failed_history
        self.failed_ttl_seconds = failed_ttl_seconds
        self._failed_meta: Dict[str, Dict[str, Any]] = {}

    def _get_call_hash(self, name: str, params: Dict[str, Any]) -> str:
        # Sort keys to ensure deterministic hashing for identical objects
        try:
            args_json = json.dumps(params, sort_keys=True)
        except (TypeError, ValueError):
            # Fallback if arguments are not JSON serializable (shouldn't happen with valid tools)
            args_json = str(sorted(params.items()))
        return hashlib.sha256(f"{name}:{args_json}".encode()).hexdigest()

    async def execute(self, name: str, params: Dict[str, Any]) -> "ToolResult":
        call_hash = self._get_call_hash(name, params)
        
        now = time.time()
        # 1. Repeat failure interception (Local Loop Protection) with TTL
        self._prune_failed(now)
        if call_hash in self.failed_call_hashes:
            logger.warning(f"Intercepted repeat failure for tool '{name}' with hash {call_hash[:8]}")
            return ToolResult(
                success=False,
                output=(
                    f"Blocked: 您刚才已经尝试过使用相同的参数调用工具 '{name}' 且失败了。\n"
                    f"请不要重复完全相同的操作（参数匹配）。您必须修改参数（例如路径、选项）或尝试其他方案。\n"
                    f"当前重复的参数: {params}"
                ),
                remedy="请检查参数是否由于路径错误或权限问题导致之前执行失败，并尝试修正它们。"
            )

        try:
            # 1. Generic Type Sanitization (Centralized Defense)
            tool = self.registry.get(name)
            if tool:
                params = self._sanitize_params(params, tool.parameters or {})

            # The registry returns a ToolResult
            res = await self.registry.execute(name, params)
            
            if not res.success:
                # Track failed calls to prevent blind repeats (with capacity limit)
                is_repeat_failure = call_hash in self._failed_meta
                if call_hash not in self.failed_call_hashes:
                    self.failed_call_hashes.add(call_hash)
                    self._failed_order.append(call_hash)
                self._failed_meta[call_hash] = {
                    "ts": now,
                    "count": (self._failed_meta.get(call_hash, {}).get("count", 0) + 1),
                }
                if len(self._failed_order) > self.max_failed_history:
                    oldest = self._failed_order.pop(0)
                    self.failed_call_hashes.discard(oldest)
                    self._failed_meta.pop(oldest, None)

                # 2. Refined Remedies (Heuristics)
                # Ensure we pass the raw output string to refine_error
                refined_msg = self._refine_error(name, params, res.output)
                
                # 3. Reflection Hinting (only on repeat failure or when remedy exists)
                if is_repeat_failure or res.remedy:
                    res.output = (
                        "[Note: 工具执行失败。在下一步之前，请先对此次失败进行反思（Thought），寻找根因并修正。]\n"
                        f"{refined_msg}"
                    )
                else:
                    res.output = refined_msg
                return res
            
            return res

        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"Unexpected error in ToolExecutor for {name}: {tb}")
            return ToolResult(
                success=False,
                output=f"Error: 内部系统错误 ({type(e).__name__}: {str(e)})。",
                remedy="建议检查您的指令输入语法，或稍后重试。若问题持续，请联系管理员。"
            )

    def _refine_error(self, name: str, params: Dict[str, Any], raw_error: str) -> str:
        """Transform technical errors into AI-actionable instructions."""
        
        error_lower = raw_error.lower()

        # File path resolution issues
        if "filenotfounderror" in error_lower or "not found" in error_lower:
            path_keys = ["path", "image_path", "target", "filename", "file"]
            path = next((params.get(k) for k in path_keys if params.get(k)), "未知路径")
            return f"{raw_error}\n建议：在使用文件相关工具前，请确认路径 '{path}' 是否正确。您可以先调用 'list_dir' 查看当前目录内容。"

        # Schema / Parameter validation
        if "invalid parameters" in error_lower or "should be" in error_lower:
            return f"{raw_error}\n建议：您的参数格式或类型似乎不正确。请仔细对比工具定义的 JSON Schema（尤其是 type 和 enum 限制）。"

        # Permission denied
        if "permission denied" in error_lower or "operation not permitted" in error_lower:
            return f"{raw_error}\n建议：权限被拒绝。请确保操作路径在工作目录内，或检查您是否有权访问该资源。"

        # Command failure
        if "exit status" in error_lower or "command failed" in error_lower:
            return f"{raw_error}\n建议：外部命令执行失败。请检查语法或依赖项是否完整。"

        return raw_error

    def _prune_failed(self, now: float) -> None:
        """Prune failed-call history by TTL."""
        if not self._failed_meta:
            return
        expired = [
            h
            for h, meta in self._failed_meta.items()
            if now - float(meta.get("ts", 0)) > self.failed_ttl_seconds
        ]
        if not expired:
            return
        for h in expired:
            self._failed_meta.pop(h, None)
            self.failed_call_hashes.discard(h)
        if expired:
            self._failed_order = [h for h in self._failed_order if h not in expired]

    def _sanitize_params(self, params: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Automatically coerce AI inputs to match schema types."""
        if not isinstance(params, dict):
            return params
            
        properties = schema.get("properties", {})
        sanitized = params.copy()
        
        for key, value in sanitized.items():
            if key not in properties:
                continue
                
            prop_schema = properties[key]
            expected_type = prop_schema.get("type")
            
            # Case 1: Enum stabilization (The "list instead of string" issue)
            if "enum" in prop_schema:
                # If it's a list but should be a string/member of enum, take the first item
                if isinstance(value, list) and len(value) > 0:
                    logger.debug(f"Coercing list to string for enum key '{key}': {value} -> {value[0]}")
                    sanitized[key] = str(value[0])
                continue

            # Case 2: Primitive type coercion
            if expected_type == "string" and not isinstance(value, str):
                sanitized[key] = str(value)
            elif expected_type == "integer" and not isinstance(value, int):
                try:
                    sanitized[key] = int(value)
                except (ValueError, TypeError):
                    pass
            elif expected_type == "boolean" and not isinstance(value, bool):
                if str(value).lower() in ("true", "1", "yes"):
                    sanitized[key] = True
                elif str(value).lower() in ("false", "0", "no"):
                    sanitized[key] = False

        return sanitized
