from __future__ import annotations
import json
from typing import AsyncIterator, Optional, Callable
from dataclasses import dataclass, field
import httpx


@dataclass
class LLMMessage:
    role: str
    content: str
    tool_calls: list = field(default_factory=list)
    tool_call_id: str = ""


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict


@dataclass
class LLMResponse:
    content: str
    tool_calls: list = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)


class LLMClient:
    def __init__(self, config):
        self.api_key = config.api_key
        self.base_url = config.base_url.rstrip("/")
        self.model = config.model
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.timeout = config.timeout
        self._client = httpx.AsyncClient(timeout=config.timeout)

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[ToolDef]] = None,
        stream: bool = False,
        response_format: Optional[dict] = None,
    ) -> LLMResponse:
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": stream,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        if response_format:
            body["response_format"] = response_format

        if stream:
            return await self._chat_stream(body)
        return await self._chat_sync(body)

    async def _chat_sync(self, body: dict) -> LLMResponse:
        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers=self._build_headers(),
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        return LLMResponse(
            content=msg.get("content", "") or "",
            tool_calls=self._parse_tool_calls(msg.get("tool_calls", [])),
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage", {}),
        )

    async def _chat_stream(self, body: dict) -> LLMResponse:
        content = ""
        tool_calls = {}
        finish_reason = ""
        async with self._client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._build_headers(),
            json=body,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                delta = data["choices"][0].get("delta", {})
                if delta.get("content"):
                    content += delta["content"]
                for tc in delta.get("tool_calls", []):
                    idx = tc["index"]
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tc.get("id", ""),
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.get("id"):
                        tool_calls[idx]["id"] = tc["id"]
                    if tc.get("function", {}).get("name"):
                        tool_calls[idx]["function"]["name"] += tc["function"]["name"]
                    if tc.get("function", {}).get("arguments"):
                        tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]
                fr = data["choices"][0].get("finish_reason")
                if fr:
                    finish_reason = fr
        return LLMResponse(
            content=content,
            tool_calls=list(tool_calls.values()),
            finish_reason=finish_reason,
        )

    def _parse_tool_calls(self, raw: list) -> list:
        result = []
        for tc in raw:
            result.append({
                "id": tc.get("id", ""),
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                },
            })
        return result

    async def chat_stream_iter(
        self,
        messages: list[dict],
        tools: Optional[list[ToolDef]] = None,
    ) -> AsyncIterator[str]:
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        async with self._client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._build_headers(),
            json=body,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                delta = data["choices"][0].get("delta", {})
                if delta.get("content"):
                    yield delta["content"]

    async def close(self):
        await self._client.aclose()
