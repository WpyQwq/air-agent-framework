from __future__ import annotations
import asyncio
import time
from typing import Optional

from .kernel import EventBus, Event, EventType
from .llm import LLMClient
from .conversation import ConversationManager


class Thinker:
    def __init__(
        self,
        bus: EventBus,
        llm: LLMClient,
        conversation: ConversationManager,
        config=None,
    ):
        self.bus = bus
        self.llm = llm
        self.conversation = conversation
        self._last_user_time = time.time()
        self._idle_threshold = (config.personality.idle_timeout
                                if config else 15)
        self._proactive = (config.personality.proactive_chat
                           if config else True)
        self._running = False
        self._last_idle_topic_time = 0.0

    async def run(self):
        self._running = True
        while self._running:
            await asyncio.sleep(5)
            if not self._proactive:
                continue
            idle_time = time.time() - self._last_user_time
            if idle_time < self._idle_threshold:
                continue
            if time.time() - self._last_idle_topic_time < 120:
                continue
            await self._generate_idle_topic(idle_time)

    def stop(self):
        self._running = False

    def notify_user_activity(self):
        self._last_user_time = time.time()

    async def _generate_idle_topic(self, idle_time: float):
        self._last_idle_topic_time = time.time()
        context = self.conversation.get_context_window(6)
        ctx_text = "\n".join(
            f"{m['role']}: {m['content'][-200:]}"
            for m in context[-4:]
        ) if context else "暂无对话"

        prompt = f"""你是一个喜欢主动聊天的 AI，当前对话已沉默 {idle_time:.0f} 秒。
最近话题:
{ctx_text}

你想开启什么话题？自然一点，像朋友随口说。
输出话题（20字内），不要解释。"""
        try:
            resp = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "简短输出一句话，20字内。"},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                max_tokens=50,
            )
            topic = resp.content.strip()
            if topic:
                await self.bus.emit(Event(
                    EventType.AGENT_THOUGHT,
                    data={"type": "idle_chat", "suggestion": topic},
                ))
        except Exception:
            pass

    async def on_input_change(self, text: str, pause: float, is_end: bool):
        pass
