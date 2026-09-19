#!/usr/bin/env python3
"""
Air Agent GUI  ——  Fluent Design 聊天界面 (PyQt5)
"""

import sys
import os

os.environ.setdefault("QT_API", "PyQt5")

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSizePolicy, QSpacerItem, QScrollBar,
)
from PyQt5.QtGui import QFont

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, ScrollArea,
    PushButton, PrimaryPushButton,
    LineEdit,
    BodyLabel, TitleLabel, CaptionLabel, SubtitleLabel, StrongBodyLabel,
    FluentIcon as FIF,
    CardWidget,
    setTheme, Theme,
    InfoBar,
    SwitchButton, SpinBox, ComboBox,
)

from config.settings import AppSettings
from gui.agent_thread import AgentThread


MSG_COLORS = {
    "user": {"bg": "#e8f0fe", "text": "#1a1a1a"},
    "assistant": {"bg": "#f0f0f0", "text": "#1a1a1a"},
    "interrupt": {"bg": "#fff8e1", "text": "#8d6e00"},
}

DARK_COLORS = {
    "user": {"bg": "#2b3a4a", "text": "#e0e0e0"},
    "assistant": {"bg": "#2d2d2d", "text": "#e0e0e0"},
    "interrupt": {"bg": "#3d3510", "text": "#ffd54f"},
}


class ChatBubble(CardWidget):
    def __init__(self, text: str, role: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.setBorderRadius(12)
        self.setMinimumHeight(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)

        label = BodyLabel(text, self)
        label.setWordWrap(True)
        label.setMinimumWidth(100)
        label.setMaximumWidth(520)
        label.setFont(QFont("Segoe UI", 10))
        self._label = label
        layout.addWidget(label)

    def apply_theme(self, is_dark: bool):
        colors = DARK_COLORS if is_dark else MSG_COLORS
        c = colors.get(self.role, colors["assistant"])
        self.setStyleSheet(f"""
            ChatBubble {{
                background-color: {c["bg"]};
                border-radius: 12px;
            }}
        """)
        self._label.setStyleSheet(f"color: {c['text']};")


class ChatPage(QWidget):
    def __init__(self, agent_thread: AgentThread, parent=None):
        super().__init__(parent)
        self.setObjectName("chatPage")
        self.agent = agent_thread
        self._bubbles = []
        self._is_streaming = False
        self._stream_bubble = None
        self._is_dark = False
        self._typing_timer = QTimer(self)
        self._typing_timer.setSingleShot(True)
        self._typing_timer.timeout.connect(self._on_typing_pause)
        self._last_input = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        tb = QWidget(self)
        tb.setFixedHeight(48)
        tbh = QHBoxLayout(tb)
        tbh.setContentsMargins(24, 8, 24, 8)
        title = TitleLabel("与 AI 聊天", tb)
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.SemiBold if hasattr(QFont.Weight, 'SemiBold') else 63))
        tbh.addWidget(title)
        tbh.addStretch()
        root.addWidget(tb)

        self._scroll = ScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setObjectName("chatScroll")
        try:
            self._scroll.enableTransparentBackground()
        except AttributeError:
            pass

        self._msg_box = QWidget()
        self._msg_box.setObjectName("msgBox")
        self._msg_layout = QVBoxLayout(self._msg_box)
        self._msg_layout.setContentsMargins(24, 8, 24, 8)
        self._msg_layout.setSpacing(8)
        self._msg_layout.setAlignment(Qt.AlignTop)

        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self._msg_layout.addSpacerItem(spacer)

        self._scroll.setWidget(self._msg_box)
        root.addWidget(self._scroll, stretch=1)

        input_area = QWidget(self)
        input_area.setFixedHeight(80)
        input_layout = QHBoxLayout(input_area)
        input_layout.setContentsMargins(24, 12, 24, 12)
        input_layout.setSpacing(8)

        self._input_edit = LineEdit(input_area)
        self._input_edit.setPlaceholderText("说点什么...")
        self._input_edit.setClearButtonEnabled(True)
        self._input_edit.setMinimumHeight(36)
        self._input_edit.returnPressed.connect(self._send_message)
        self._input_edit.textChanged.connect(self._on_text_changed)

        self._send_btn = PrimaryPushButton(FIF.SEND, "发送", input_area)
        self._send_btn.setFixedHeight(36)
        self._send_btn.clicked.connect(self._send_message)

        self._indicator = BodyLabel("", input_area)
        self._indicator.setFixedWidth(80)
        self._indicator.setAlignment(Qt.AlignCenter)

        input_layout.addWidget(self._input_edit, stretch=1)
        input_layout.addWidget(self._send_btn)
        input_layout.addWidget(self._indicator)

        root.addWidget(input_area)

        self.agent.message_chunk.connect(self._on_chunk)
        self.agent.message_done.connect(self._on_message_done)
        self.agent.agent_thinking.connect(self._on_thinking)
        self.agent.agent_idle.connect(self._on_idle)
        self.agent.error_occurred.connect(self._on_error)
        self.agent.interrupt_signal.connect(self._on_interrupt)
        self.agent.idle_topic_signal.connect(self._on_idle_topic)

    def _on_text_changed(self, text: str):
        if text and text != self._last_input:
            self._last_input = text
            self._typing_timer.start(2000)
        elif not text:
            self._last_input = ""

    def _on_typing_pause(self):
        text = self._input_edit.text()
        if len(text) > 3:
            self.agent.check_interruption(text, 2.0)

    def _send_message(self):
        text = self._input_edit.text().strip()
        if not text or self._is_streaming:
            return
        self._input_edit.clear()
        self._typing_timer.stop()
        self._last_input = ""
        self._add_bubble(text, "user")
        self.agent.send_message(text)

    def _add_bubble(self, text: str, role: str):
        bubble = ChatBubble(text, role, self._msg_box)
        bubble.apply_theme(self._is_dark)
        row = QHBoxLayout()
        if role == "user":
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()
        self._msg_layout.insertLayout(self._msg_layout.count() - 1, row)
        self._bubbles.append(bubble)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _on_chunk(self, chunk: str):
        if not self._is_streaming:
            self._is_streaming = True
            self._indicator.setText("输入中...")
            bubble = ChatBubble("", "assistant", self._msg_box)
            bubble.apply_theme(self._is_dark)
            row = QHBoxLayout()
            row.addWidget(bubble)
            row.addStretch()
            self._msg_layout.insertLayout(self._msg_layout.count() - 1, row)
            self._stream_bubble = bubble
            self._bubbles.append(bubble)
        if self._stream_bubble:
            current = self._stream_bubble._label.text()
            self._stream_bubble._label.setText(current + chunk)
            self._scroll_to_bottom()

    def _on_message_done(self, full: str):
        self._is_streaming = False
        self._stream_bubble = None
        self._indicator.setText("")

    def _on_thinking(self):
        self._indicator.setText("思考中...")

    def _on_idle(self):
        self._indicator.setText("")

    def _on_error(self, msg: str):
        self._indicator.setText("")
        InfoBar.error("错误", msg, duration=5000, parent=self.window())

    def _on_interrupt(self, response: str, style: str):
        text = f"[插话] {response}"
        self._add_bubble(text, "interrupt")

    def _on_idle_topic(self, suggestion: str):
        text = f"[主动] {suggestion}"
        self._add_bubble(text, "interrupt")

    def set_theme(self, dark: bool):
        self._is_dark = dark
        for b in self._bubbles:
            b.apply_theme(dark)


class SettingsPage(QWidget):
    def __init__(self, config: AppSettings, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.config = config

        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        try:
            scroll.enableTransparentBackground()
        except AttributeError:
            pass

        inner = QWidget()
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(36, 24, 36, 24)
        vl.setSpacing(16)

        vl.addWidget(TitleLabel("设置", inner))
        vl.addSpacing(8)

        vl.addWidget(SubtitleLabel("API 配置"))
        api_card = CardWidget(inner)
        ac = QVBoxLayout(api_card)
        ac.setContentsMargins(20, 14, 20, 14)
        ac.setSpacing(8)

        ac.addWidget(BodyLabel("API Key："))
        self.key_edit = LineEdit(api_card)
        self.key_edit.setText(config.llm.api_key)
        self.key_edit.setEchoMode(2)
        self.key_edit.setClearButtonEnabled(True)
        ac.addWidget(self.key_edit)

        ac.addWidget(BodyLabel("Base URL："))
        self.url_edit = LineEdit(api_card)
        self.url_edit.setText(config.llm.base_url)
        self.url_edit.setClearButtonEnabled(True)
        ac.addWidget(self.url_edit)

        ac.addWidget(BodyLabel("Model："))
        self.model_edit = LineEdit(api_card)
        self.model_edit.setText(config.llm.model)
        self.model_edit.setClearButtonEnabled(True)
        ac.addWidget(self.model_edit)

        apply_api_btn = PushButton("保存 API 设置", api_card)
        apply_api_btn.clicked.connect(self._save_api)
        ac.addWidget(apply_api_btn)
        vl.addWidget(api_card)

        vl.addWidget(SubtitleLabel("对话设置"))
        chat_card = CardWidget(inner)
        cc = QVBoxLayout(chat_card)
        cc.setContentsMargins(20, 14, 20, 14)
        cc.setSpacing(8)

        cc.addWidget(BodyLabel("AI 名字："))
        self.name_edit = LineEdit(chat_card)
        self.name_edit.setText(config.personality.name)
        cc.addWidget(self.name_edit)

        cc.addWidget(BodyLabel("对话风格："))
        self.style_combo = ComboBox(chat_card)
        self.style_combo.addItems(["casual", "friendly", "professional"])
        idx = self.style_combo.findText(config.personality.style)
        if idx >= 0:
            self.style_combo.setCurrentIndex(idx)
        cc.addWidget(self.style_combo)

        cc.addWidget(BodyLabel("空闲主动聊天："))
        self.proactive_switch = SwitchButton(chat_card)
        self.proactive_switch.setChecked(config.personality.proactive_chat)
        cc.addWidget(self.proactive_switch)

        apply_chat_btn = PushButton("保存对话设置", chat_card)
        apply_chat_btn.clicked.connect(self._save_chat)
        cc.addWidget(apply_chat_btn)
        vl.addWidget(chat_card)

        vl.addWidget(SubtitleLabel("外观"))
        theme_card = CardWidget(inner)
        tl = QHBoxLayout(theme_card)
        tl.setContentsMargins(20, 14, 20, 14)
        tl.setSpacing(12)
        tl.addWidget(BodyLabel("深色模式："))
        self.theme_switch = SwitchButton(theme_card)
        self.theme_switch.checkedChanged.connect(self._toggle_theme)
        tl.addWidget(self.theme_switch)
        tl.addStretch()
        vl.addWidget(theme_card)

        vl.addStretch()
        scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def _save_api(self):
        self.config.llm.api_key = self.key_edit.text().strip()
        self.config.llm.base_url = self.url_edit.text().strip()
        self.config.llm.model = self.model_edit.text().strip()
        self.config.save()
        InfoBar.success("已保存", "API 配置已保存，重启后生效", duration=3000, parent=self.window())

    def _save_chat(self):
        self.config.personality.name = self.name_edit.text().strip()
        self.config.personality.style = self.style_combo.currentText()
        self.config.personality.proactive_chat = self.proactive_switch.isChecked()
        self.config.save()
        InfoBar.success("已保存", "对话设置已保存，重启后生效", duration=3000, parent=self.window())

    def _toggle_theme(self, dark: bool):
        setTheme(Theme.DARK if dark else Theme.LIGHT)
        main = self.window()
        if hasattr(main, "chat_page"):
            main.chat_page.set_theme(dark)


class AgentWindow(FluentWindow):
    def __init__(self, config: AppSettings):
        super().__init__()
        self.config = config
        self.setWindowTitle("Air Agent")
        self.setMinimumSize(800, 560)
        self.resize(1000, 680)

        self.agent_thread = AgentThread(config)
        self.chat_page = ChatPage(self.agent_thread, self)
        self.settings_page = SettingsPage(config, self)

        self.addSubInterface(
            self.chat_page, FIF.CHAT, "聊天", NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.settings_page, FIF.SETTING, "设置", NavigationItemPosition.BOTTOM
        )

        setTheme(Theme.LIGHT)
        self.agent_thread.start()

    def closeEvent(self, event):
        self.agent_thread.stop_agent()
        self.agent_thread.quit()
        self.agent_thread.wait(3000)
        super().closeEvent(event)


def run_gui(config: AppSettings):
    app = QApplication(sys.argv)
    app.setApplicationName("Air Agent")

    win = AgentWindow(config)
    win.show()
    sys.exit(app.exec())
