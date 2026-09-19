from __future__ import annotations
from typing import Any, Callable, Awaitable, Optional

from ..llm import ToolDef


ToolHandler = Callable[..., Awaitable[str]]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, tuple[ToolDef, ToolHandler]] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: ToolHandler,
    ):
        self._tools[name] = (
            ToolDef(name=name, description=description, parameters=parameters),
            handler,
        )

    def get_defs(self) -> list[ToolDef]:
        return [t[0] for t in self._tools.values()]

    def get_handler(self, name: str) -> Optional[ToolHandler]:
        entry = self._tools.get(name)
        return entry[1] if entry else None

    async def execute(self, name: str, **kwargs) -> str:
        handler = self.get_handler(name)
        if not handler:
            return f"[错误: 工具 '{name}' 不存在]"
        try:
            return await handler(**kwargs)
        except Exception as e:
            return f"[工具 '{name}' 执行失败: {e}]"

    def tool(self, name: str, description: str, parameters: dict):
        def decorator(func: ToolHandler):
            self.register(name, description, parameters, func)
            return func
        return decorator
