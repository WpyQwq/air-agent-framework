from __future__ import annotations
from .registry import ToolRegistry


def register_ask_tools(registry: ToolRegistry):

    @registry.tool(
        name="ask_user",
        description="向用户提问，等待用户回答。用于需要澄清或获取信息时。",
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "要问用户的问题",
                },
            },
            "required": ["question"],
        },
    )
    async def ask_user(question: str) -> str:
        return f"[等待用户回答: {question}]"
