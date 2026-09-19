from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Topic:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    active: bool = True
    parent_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


@dataclass
class ConversationMessage:
    role: str
    content: str
    topic_id: str = ""
    timestamp: float = field(default_factory=time.time)


class ConversationManager:
    def __init__(self, max_context_tokens: int = 8000):
        self.topics: dict[str, Topic] = {}
        self.messages: list[ConversationMessage] = []
        self.current_topic_id: Optional[str] = None
        self.max_context_tokens = max_context_tokens
        self._llm_messages: list[dict] = []

    def create_topic(self, title: str, parent_id: Optional[str] = None) -> str:
        topic = Topic(title=title, parent_id=parent_id)
        self.topics[topic.id] = topic
        self.current_topic_id = topic.id
        return topic.id

    def switch_topic(self, topic_id: str):
        if topic_id in self.topics:
            self.current_topic_id = topic_id
            self.topics[topic_id].last_active = time.time()

    def add_message(self, role: str, content: str, topic_id: Optional[str] = None):
        msg = ConversationMessage(
            role=role,
            content=content,
            topic_id=topic_id or self.current_topic_id or "",
        )
        self.messages.append(msg)
        self._llm_messages.append({"role": role, "content": content})

    def get_llm_messages(self) -> list[dict]:
        return self._llm_messages.copy()

    def get_context_window(self, max_messages: int = 30) -> list[dict]:
        msgs = self._llm_messages[-max_messages:]
        return msgs

    def get_topic_tree(self) -> list[dict]:
        roots = []
        child_map: dict[str, list[Topic]] = {}
        for t in self.topics.values():
            if t.parent_id:
                child_map.setdefault(t.parent_id, []).append(t)
            else:
                roots.append(t)

        def build(node: Topic) -> dict:
            return {
                "id": node.id,
                "title": node.title,
                "active": node.active,
                "children": [build(c) for c in child_map.get(node.id, [])],
            }

        return [build(r) for r in roots]

    def archive_topic(self, topic_id: str):
        if topic_id in self.topics:
            self.topics[topic_id].active = False

    def summarize_old_messages(self):
        if len(self._llm_messages) > 50:
            old = self._llm_messages[:-30]
            summary = f"[已省略 {len(old)} 条历史消息]"
            self._llm_messages = [{"role": "system", "content": f"记忆摘要: {summary}"}] + self._llm_messages[-30:]
