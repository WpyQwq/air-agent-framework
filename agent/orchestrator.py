from __future__ import annotations
from enum import Enum

from .kernel import EventBus, Event, EventType, AgentRuntime
from .llm import LLMClient
from .personality import Personality
from .conversation import ConversationManager
from .interruption import InterruptionEngine
from .thinker import Thinker


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    RESPONDING = "responding"
    QUESTIONING = "questioning"
    WAITING_INPUT = "waiting_input"


class Orchestrator:
    def __init__(
        self,
        runtime: AgentRuntime,
        llm: LLMClient,
        personality: Personality,
        conversation: ConversationManager,
        interruption: InterruptionEngine,
        thinker: Thinker,
    ):
        self.runtime = runtime
        self.bus = runtime.bus
        self.llm = llm
        self.personality = personality
        self.conversation = conversation
        self.interruption = interruption
        self.thinker = thinker
        self.state = AgentState.IDLE
        self._response_task = None

    async def generate_response(self, messages: list[dict]) -> str:
        system_prompt = self.personality.build_system_prompt()
        full = [{"role": "system", "content": system_prompt}] + messages
        resp = await self.llm.chat(full, stream=False)
        return resp.content

    async def stream_response(self, messages: list[dict]) -> str:
        system_prompt = self.personality.build_system_prompt()
        full = [{"role": "system", "content": system_prompt}] + messages
        full_text = ""
        async for chunk in self.llm.chat_stream_iter(full):
            full_text += chunk
            await self.bus.emit(Event(
                EventType.AGENT_STREAM_CHUNK,
                {"chunk": chunk, "full": full_text},
            ))
        return full_text

    async def generate_single_response(self, messages: list[dict]) -> str:
        return await self.generate_response(messages)
