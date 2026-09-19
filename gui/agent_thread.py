from __future__ import annotations
import asyncio
import sys
from PyQt5.QtCore import QThread, pyqtSignal

from agent.kernel import EventBus, Event, EventType, AgentRuntime
from agent.llm import LLMClient
from agent.personality import Personality
from agent.conversation import ConversationManager
from agent.interruption import InterruptionEngine
from agent.thinker import Thinker
from agent.orchestrator import Orchestrator
from agent.tools.registry import ToolRegistry
from agent.tools.file_tools import register_file_tools
from agent.tools.bash_tools import register_bash_tools
from agent.tools.ask import register_ask_tools

from config.settings import AppSettings


class AgentThread(QThread):
    message_chunk = pyqtSignal(str)
    message_done = pyqtSignal(str)
    agent_thinking = pyqtSignal()
    agent_idle = pyqtSignal()
    error_occurred = pyqtSignal(str)
    interrupt_signal = pyqtSignal(str, str)
    idle_topic_signal = pyqtSignal(str)

    def __init__(self, config: AppSettings):
        super().__init__()
        self.config = config
        self._loop: asyncio.AbstractEventLoop = None
        self._running = False
        self._input_queue: asyncio.Queue[str] = None

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_agent())

    async def _run_agent(self):
        self._input_queue = asyncio.Queue()
        self._running = True

        runtime = AgentRuntime(self.config)
        llm = LLMClient(self.config.llm)
        bus = runtime.bus
        personality = Personality.from_config({
            "name": self.config.personality.name,
            "style": self.config.personality.style,
            "proactive_chat": self.config.personality.proactive_chat,
            "idle_timeout": self.config.personality.idle_timeout,
            "humor_enabled": self.config.personality.humor_enabled,
            "empathy_enabled": self.config.personality.empathy_enabled,
        })
        conversation = ConversationManager()
        interruption = InterruptionEngine(llm=llm, config=self.config)
        thinker = Thinker(bus, llm, conversation, self.config)
        orchestrator = Orchestrator(runtime, llm, personality, conversation, interruption, thinker)

        conversation.create_topic("general")
        await runtime.start()

        thinker_task = runtime.create_task(thinker.run())

        async def on_thought(event: Event):
            data = event.data
            if data.get("type") == "idle_chat":
                self.idle_topic_signal.emit(data.get("suggestion", ""))

        bus.on(EventType.AGENT_THOUGHT, on_thought)

        try:
            while self._running:
                try:
                    user_text = await asyncio.wait_for(
                        self._input_queue.get(), timeout=0.5
                    )
                except asyncio.TimeoutError:
                    continue

                thinker.notify_user_activity()
                conversation.add_message("user", user_text)
                self.agent_thinking.emit()

                system_prompt = personality.build_system_prompt()
                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(conversation.get_context_window(20))

                try:
                    full = ""
                    async for chunk in llm.chat_stream_iter(messages):
                        full += chunk
                        self.message_chunk.emit(chunk)
                    self.message_done.emit(full)
                    if full.strip():
                        conversation.add_message("assistant", full)
                except Exception as e:
                    self.error_occurred.emit(str(e))

                self.agent_idle.emit()

        finally:
            await runtime.stop()
            await llm.close()

    def send_message(self, text: str):
        if self._input_queue and self._running:
            asyncio.run_coroutine_threadsafe(
                self._input_queue.put(text), self._loop
            )

    def check_interruption(self, partial_text: str, pause: float):
        if not self._running or not self._loop:
            return
        config = self.config
        llm = LLMClient(config.llm)
        engine = InterruptionEngine(llm=llm, config=config)

        async def _check():
            decision = await engine.evaluate(partial_text, pause, False)
            if decision.should_interrupt:
                self.interrupt_signal.emit(
                    decision.suggested_response, decision.style
                )

        asyncio.run_coroutine_threadsafe(_check(), self._loop)

    def stop_agent(self):
        self._running = False
