from __future__ import annotations
import asyncio
import sys

from agent.kernel import Event, EventType, AgentRuntime
from agent.llm import LLMClient
from agent.personality import Personality
from agent.conversation import ConversationManager
from agent.interruption import InterruptionEngine, InterruptionDecision
from agent.thinker import Thinker
from agent.orchestrator import Orchestrator
from agent.stream_input import StreamInput
from agent.display import Display

from config.settings import AppSettings


class ChatCLI:
    def __init__(self, config: AppSettings):
        self.config = config
        self.runtime = AgentRuntime(config)
        self.llm = LLMClient(config.llm)
        self.bus = self.runtime.bus
        self.personality = Personality.from_config({
            "name": config.personality.name,
            "style": config.personality.style,
            "proactive_chat": config.personality.proactive_chat,
            "idle_timeout": config.personality.idle_timeout,
            "humor_enabled": config.personality.humor_enabled,
            "empathy_enabled": config.personality.empathy_enabled,
        })
        self.conversation = ConversationManager()
        self.interruption = InterruptionEngine(llm=self.llm, config=config)
        self.thinker = Thinker(self.bus, self.llm, self.conversation, config)
        self.orchestrator = Orchestrator(
            self.runtime, self.llm, self.personality,
            self.conversation, self.interruption, self.thinker,
        )
        self.display = Display(self.bus)
        self.stream_input = StreamInput(self.bus)
        self.conversation.create_topic("general")

        self.bus.on(EventType.USER_PAUSE, self._on_user_pause)
        self.bus.on(EventType.AGENT_THOUGHT, self._on_thought)

    async def _on_thought(self, event: Event):
        data = event.data
        if data.get("type") == "idle_chat":
            topic = data.get("suggestion", "")
            print(f"\n\033[90m[AI 在想：{topic}]\033[0m")

    async def _on_user_pause(self, event: Event):
        data = event.data
        text = data.get("text", "")
        pause = data.get("pause", 0)
        context = self.conversation.get_context_window(6)
        decision = await self.interruption.evaluate(
            text, pause, False, context=context,
        )
        if decision.should_interrupt:
            self.thinker.notify_user_activity()
            resp = decision.suggested_response or "..."
            print(f"\n\033[33m[打断]\033[0m \033[36m{self.personality.name}\033[0m {resp}")
            self.display.show_prompt()

    async def _handle_message(self, text: str):
        self.thinker.notify_user_activity()
        self.conversation.add_message("user", text)
        system_prompt = self.personality.build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation.get_context_window(20))
        print(f"\n\033[36m{self.personality.name}\033[0m ", end="")
        full = ""
        try:
            async for chunk in self.llm.chat_stream_iter(messages):
                print(chunk, end="", flush=True)
                full += chunk
            print()
        except Exception as e:
            print(f"\n\033[31m[错误: {e}]\033[0m")
        if full.strip():
            self.conversation.add_message("assistant", full)

    async def run(self):
        self.display.show_startup()
        await self.runtime.start()
        thinker_task = self.runtime.create_task(self.thinker.run())

        async def on_sentence(text: str):
            await self._handle_message(text)

        try:
            self.display.show_prompt()
            await self.stream_input.listen_cli(on_sentence=on_sentence)
        except KeyboardInterrupt:
            print("\n再见！")
        finally:
            await self.runtime.stop()
            await self.llm.close()
