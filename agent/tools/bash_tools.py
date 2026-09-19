from __future__ import annotations
import asyncio

from .registry import ToolRegistry


def register_bash_tools(registry: ToolRegistry):

    @registry.tool(
        name="run_command",
        description="执行 shell 命令并返回输出",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
    )
    async def run_command(command: str, timeout: int = 30) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                return f"[命令超时 ({timeout}s)]"
            output = ""
            if stdout:
                output += stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n[STDERR]\n" + stderr.decode("utf-8", errors="replace")
            if len(output) > 5000:
                output = output[:5000] + "\n\n[输出过长，已截断]"
            return output or "[无输出]"
        except Exception as e:
            return f"[命令执行失败: {e}]"
