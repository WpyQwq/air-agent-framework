from __future__ import annotations
import asyncio
import sys
import shutil
from datetime import datetime

from .kernel import EventBus, Event, EventType


COLOR_RESET = "\033[0m"
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_GRAY = "\033[90m"
COLOR_RED = "\033[31m"
COLOR_BOLD = "\033[1m"

USE_COLOR = sys.stdout.isatty()

GRAY = "\033[90m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


class Display:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self._output_buffer = ""
        self._input_line = ""
        self._running = False

        bus.on(EventType.AGENT_STREAM_CHUNK, self._on_chunk)
        bus.on(EventType.AGENT_MESSAGE, self._on_message)
        bus.on(EventType.AGENT_THOUGHT, self._on_thought)
        bus.on(EventType.INTERRUPT, self._on_interrupt)
        bus.on(EventType.ERROR, self._on_error)
        bus.on(EventType.USER_INPUT_CHANGE, self._on_input_change)

    async def _on_chunk(self, event: Event):
        data = event.data
        chunk = data["chunk"]
        if not USE_COLOR:
            print(chunk, end="", flush=True)
            return
        print(chunk, end="", flush=True)

    async def _on_message(self, event: Event):
        if USE_COLOR:
            print(f"\n{GREEN}───{RESET}")
        else:
            print()

    async def _on_thought(self, event: Event):
        data = event.data
        if data.get("type") == "idle_chat":
            suggestion = data.get("suggestion", "")
            if USE_COLOR:
                print(f"\n{GRAY}[思考中... {suggestion}]{RESET}")
            else:
                print(f"\n[思考中... {suggestion}]")

    async def _on_interrupt(self, event: Event):
        if not USE_COLOR:
            print("\n[打断]")
            return
        print(f"\n{YELLOW}⚡ [打断]{RESET}")

    async def _on_error(self, event: Event):
        msg = event.data
        if USE_COLOR:
            print(f"\n{RED}✗ 错误: {msg}{RESET}")
        else:
            print(f"\n✗ 错误: {msg}")

    async def _on_input_change(self, event: Event):
        pass

    def show_prompt(self):
        prompt = f"\n{COLOR_CYAN}你{COLOR_RESET} "
        print(prompt, end="", flush=True)

    def show_startup(self):
        cols = shutil.get_terminal_size().columns
        print(f"{GREEN}{'='*cols}{RESET}")
        print(f"{GREEN}{BOLD}  Air Agent  🤖  —  随时插嘴，想聊就聊{RESET}")
        print(f"{GREEN}{'='*cols}{RESET}")
        print(f"{GRAY}  直接打字聊天，试试说到一半停顿一下...{RESET}")
        print()
