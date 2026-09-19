from __future__ import annotations
import asyncio
import time
import sys
from typing import Optional

from .kernel import EventBus, Event, EventType


try:
    import msvcrt

    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False


class InputBuffer:
    def __init__(self):
        self.text = ""
        self.last_key_time = time.time()
        self.pause_start: Optional[float] = None
        self.sentence_boundaries = {'.', '!', '?', '。', '！', '？', '\n'}
        self._committed = ""

    def add_char(self, char: str):
        now = time.time()
        pause = now - self.last_key_time
        if pause > 0.3 and self.text:
            self.pause_start = now
        else:
            self.pause_start = None
        self.last_key_time = now

        if char == '\r':
            self._committed = self.text
            self.text = ""
            return True
        elif char == '\b' or char == '\x7f':
            self.text = self.text[:-1]
        else:
            self.text += char
        return False

    @property
    def current_pause(self) -> float:
        if not self.text:
            return 0.0
        return time.time() - self.last_key_time

    @property
    def is_at_sentence_end(self) -> bool:
        return bool(self.text) and self.text[-1] in self.sentence_boundaries

    @property
    def committed(self) -> str:
        return self._committed

    def reset_committed(self):
        self._committed = ""

    def __repr__(self):
        return f"InputBuffer(text='{self.text}', pause={self.current_pause:.2f}s)"


class StreamInput:
    def __init__(self, bus: EventBus, buffer: Optional[InputBuffer] = None):
        self.bus = bus
        self.buffer = buffer or InputBuffer()
        self._running = False

    async def listen_cli(self, on_sentence=None):
        self._running = True
        if not HAS_MSVCRT:
            print("[Air] 当前环境不支持实时按键捕获，使用标准输入模式。")
            await self._listen_fallback(on_sentence)
            return

        while self._running:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch == '\x03':
                    raise KeyboardInterrupt
                if ch == '\xe0':
                    ch2 = msvcrt.getwch()
                    if ch2 == 'K':
                        continue
                    if ch2 == 'M':
                        continue
                    continue
                is_commit = self.buffer.add_char(ch)
                await self.bus.emit(Event(
                    EventType.USER_INPUT_CHANGE,
                    {
                        "text": self.buffer.text,
                        "pause": self.buffer.current_pause,
                        "is_end": self.buffer.is_at_sentence_end or is_commit,
                    },
                ))
                if is_commit and self.buffer.committed.strip():
                    text = self.buffer.committed.strip()
                    self.buffer.reset_committed()
                    await self.bus.emit(Event(EventType.USER_MESSAGE, text))
                    if on_sentence:
                        await on_sentence(text)
            else:
                await asyncio.sleep(0.05)
                if self.buffer.text and self.buffer.current_pause > 3.0:
                    await self.bus.emit(Event(
                        EventType.USER_PAUSE,
                        {
                            "text": self.buffer.text,
                            "pause": self.buffer.current_pause,
                        },
                    ))

    async def _listen_fallback(self, on_sentence=None):
        while self._running:
            line = await asyncio.get_event_loop().run_in_executor(
                None, sys.stdin.readline
            )
            line = line.strip()
            if line:
                await self.bus.emit(Event(EventType.USER_MESSAGE, line))
                if on_sentence:
                    await on_sentence(line)

    def stop(self):
        self._running = False
