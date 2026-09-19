from __future__ import annotations
import time
from enum import IntEnum
from dataclasses import dataclass, field
from typing import Optional


class InterruptLevel(IntEnum):
    LIGHT = 1
    MEDIUM = 4
    HIGH = 7
    URGENT = 10


@dataclass
class InterruptionDecision:
    should_interrupt: bool = False
    level: InterruptLevel = InterruptLevel.LIGHT
    style: str = "light"
    reason: str = ""
    suggested_response: str = ""


class InterruptionEngine:
    def __init__(self, llm=None, config=None):
        self.llm = llm
        self.config = config
        self._last_interrupt_time = 0.0
        self._interrupt_times: list[float] = []
        self._cooldown = (config.interruption.cooldown_seconds
                          if config else 3.0)
        self._max_per_minute = (config.interruption.max_per_minute
                                if config else 6)
        self._enabled = (config.interruption.enabled
                         if config else True)

    async def evaluate(
        self,
        input_buffer: str,
        pause_duration: float,
        is_sentence_end: bool,
        context: list[dict] | None = None,
    ) -> InterruptionDecision:
        if not self._enabled or not input_buffer.strip():
            return InterruptionDecision()
        if not self._can_interrupt():
            return InterruptionDecision()

        if self.llm:
            return await self._llm_judge(input_buffer, pause_duration, context)
        return InterruptionDecision()

    def _can_interrupt(self) -> bool:
        now = time.time()
        if now - self._last_interrupt_time < self._cooldown:
            return False
        recent = [t for t in self._interrupt_times if now - t < 60]
        if len(recent) >= self._max_per_minute:
            return False
        return True

    def _record_interrupt(self):
        self._last_interrupt_time = time.time()
        self._interrupt_times.append(time.time())
        self._interrupt_times = [
            t for t in self._interrupt_times if time.time() - t < 60
        ]

    async def _llm_judge(
        self, text: str, pause: float, context: list[dict] | None
    ) -> InterruptionDecision:
        ctx_preview = ""
        if context:
            ctx_preview = "\n".join(
                f"{m['role']}: {m['content'][-100:]}"
                for m in context[-4:]
            )

        prompt = f"""判断是否需要 AI 插话。

用户当前输入（未完成）: "{text}"
用户停顿: {pause:.1f}秒
最近对话:
{ctx_preview}

请输出 JSON:
{{
  "should_interrupt": true/false,
  "priority": "low/medium/high",
  "style": "light/question/excited/strong",
  "reason": "简短原因",
  "suggested_response": "一句话（15字内）"
}}
规则：低优先级打断频率 < 2次/分钟。宁可少打断，不要过度打断。"""
        try:
            resp = await self.llm.chat(
                messages=[
                    {"role": "system", "content": "输出JSON，不要其他内容。"},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                stream=False,
            )
            import json
            data = json.loads(resp.content)
            if data.get("should_interrupt"):
                self._record_interrupt()
                level_map = {"low": InterruptLevel.LIGHT,
                             "medium": InterruptLevel.MEDIUM,
                             "high": InterruptLevel.HIGH}
                return InterruptionDecision(
                    should_interrupt=True,
                    level=level_map.get(data.get("priority", "low"), InterruptLevel.LIGHT),
                    style=data.get("style", "light"),
                    reason=data.get("reason", ""),
                    suggested_response=data.get("suggested_response", ""),
                )
        except Exception:
            pass
        return InterruptionDecision()
