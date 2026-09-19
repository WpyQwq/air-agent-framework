from dataclasses import dataclass, field
from typing import Optional
import json
import os


@dataclass
class LLMSettings:
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60


@dataclass
class InterruptionSettings:
    enabled: bool = True
    cooldown_seconds: float = 3.0
    pause_threshold: float = 1.5
    max_per_minute: int = 6


@dataclass
class PersonalitySettings:
    name: str = "Air"
    style: str = "casual"
    proactive_chat: bool = True
    idle_timeout: int = 15
    humor_enabled: bool = True
    empathy_enabled: bool = True


@dataclass
class AppSettings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    interruption: InterruptionSettings = field(default_factory=InterruptionSettings)
    personality: PersonalitySettings = field(default_factory=PersonalitySettings)
    data_dir: str = os.path.expanduser("~/.air_agent")

    def save(self, path: str = ""):
        path = path or os.path.join(self.data_dir, "config.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "llm": {
                    "provider": self.llm.provider,
                    "model": self.llm.model,
                    "api_key": self.llm.api_key,
                    "base_url": self.llm.base_url,
                    "max_tokens": self.llm.max_tokens,
                    "temperature": self.llm.temperature,
                    "timeout": self.llm.timeout,
                },
                "interruption": {
                    "enabled": self.interruption.enabled,
                    "cooldown_seconds": self.interruption.cooldown_seconds,
                    "pause_threshold": self.interruption.pause_threshold,
                    "max_per_minute": self.interruption.max_per_minute,
                },
                "personality": {
                    "name": self.personality.name,
                    "style": self.personality.style,
                    "proactive_chat": self.personality.proactive_chat,
                    "idle_timeout": self.personality.idle_timeout,
                    "humor_enabled": self.personality.humor_enabled,
                    "empathy_enabled": self.personality.empathy_enabled,
                },
                "data_dir": self.data_dir,
            }, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str = "") -> "AppSettings":
        path = path or os.path.join(os.path.expanduser("~/.air_agent"), "config.json")
        if not os.path.exists(path):
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        llm_data = data.get("llm", {})
        int_data = data.get("interruption", {})
        per_data = data.get("personality", {})
        return cls(
            llm=LLMSettings(**llm_data),
            interruption=InterruptionSettings(**int_data),
            personality=PersonalitySettings(**per_data),
            data_dir=data.get("data_dir", cls().data_dir),
        )
