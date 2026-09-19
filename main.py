#!/usr/bin/env python3
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import AppSettings


def run_cli():
    from cli.chat_cli import ChatCLI
    cli = ChatCLI(config)
    asyncio.run(cli.run())


def run_gui():
    from gui.chat_gui import run_gui as gui_main
    gui_main(config)


def first_time_setup():
    print("=" * 50)
    print("  Air Agent  — 首次运行配置")
    print("=" * 50)
    config.llm.api_key = input("OpenAI API Key: ").strip()
    config.llm.base_url = input(f"Base URL [{config.llm.base_url}]: ").strip() or config.llm.base_url
    config.llm.model = input(f"Model [{config.llm.model}]: ").strip() or config.llm.model
    config.save()
    print("配置已保存到 ~/.air_agent/config.json\n")


if __name__ == "__main__":
    config = AppSettings.load()

    if not config.llm.api_key:
        first_time_setup()

    mode = "gui"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    if mode == "cli":
        run_cli()
    else:
        try:
            run_gui()
        except ImportError as e:
            print(f"GUI 模式需要 PyQt6 + qfluentwidgets: pip install PyQt6 qfluentwidgets")
            print(f"导入错误: {e}")
            print("切换到 CLI 模式...")
            run_cli()
