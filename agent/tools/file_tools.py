from __future__ import annotations
import os

from .registry import ToolRegistry


def register_file_tools(registry: ToolRegistry):

    @registry.tool(
        name="read_file",
        description="读取文件内容",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
            },
            "required": ["path"],
        },
    )
    async def read_file(path: str) -> str:
        if not os.path.exists(path):
            return f"[文件不存在: {path}]"
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 10000:
            content = content[:10000] + "\n\n[内容过长，已截断]"
        return content

    @registry.tool(
        name="write_file",
        description="写入文件",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["path", "content"],
        },
    )
    async def write_file(path: str, content: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[已写入 {len(content)} 字节到 {path}]"

    @registry.tool(
        name="list_files",
        description="列出目录内容",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径",
                },
            },
            "required": ["path"],
        },
    )
    async def list_files(path: str = ".") -> str:
        if not os.path.exists(path):
            return f"[目录不存在: {path}]"
        items = os.listdir(path)
        lines = []
        for item in sorted(items):
            full = os.path.join(path, item)
            suffix = "/" if os.path.isdir(full) else ""
            lines.append(f"  {item}{suffix}")
        return f"{path} ({len(lines)} 项):\n" + "\n".join(lines)
