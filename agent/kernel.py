from __future__ import annotations
import asyncio
import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


class EventType(Enum):
    USER_MESSAGE = "user_message"
    USER_INPUT_CHANGE = "user_input_change"
    USER_PAUSE = "user_pause"
    USER_RESUME = "user_resume"
    AGENT_MESSAGE = "agent_message"
    AGENT_THOUGHT = "agent_thought"
    AGENT_STREAM_CHUNK = "agent_stream_chunk"
    INTERRUPT = "interrupt"
    QUESTION = "question"
    QUESTION_ANSWER = "question_answer"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATE_CHANGE = "state_change"
    IDLE = "idle"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class Event:
    type: EventType
    data: Any = None
    source: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)

    def __repr__(self):
        return f"[{self.type.value}] {self.data}"


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self):
        self._listeners: dict[EventType, list[EventHandler]] = {}
        self._history: list[Event] = []
        self._max_history = 1000

    def on(self, event_type: EventType, handler: EventHandler):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(handler)

    def off(self, event_type: EventType, handler: EventHandler):
        if event_type in self._listeners:
            self._listeners[event_type].remove(handler)

    async def emit(self, event: Event):
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        handlers = self._listeners.get(event.type, [])
        results = []
        for handler in handlers:
            try:
                results.append(handler(event))
            except Exception as e:
                import traceback
                traceback.print_exc()
        if results:
            await asyncio.gather(*results)

    def get_history(self, limit: int = 50) -> list[Event]:
        return self._history[-limit:]


class AgentRuntime:
    def __init__(self, config: Any = None):
        self.bus = EventBus()
        self.config = config
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._running

    def create_task(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def start(self):
        self._running = True
        self._shutdown_event.clear()

    async def stop(self):
        self._running = False
        await self.bus.emit(Event(EventType.SHUTDOWN))
        self._shutdown_event.set()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def wait_for_shutdown(self):
        await self._shutdown_event.wait()
