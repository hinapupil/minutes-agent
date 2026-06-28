from __future__ import annotations

from typing import Any

from agent.tools import (
    extract_action_items,
    generate_minutes,
    get_pending_actions,
    search_minutes,
    send_discord_message,
    transcribe_audio,
)
from minutes_agent.config import Settings, get_settings

AGENT_INSTRUCTION = """\
あなたは会議のアカウンタビリティ・エージェントです。
会議の継続性と実行責任を管理します。

責務:
1. 録音された音声を文字起こしし、構造化された議事録を生成する
2. 議事録からアクションアイテムを自動抽出する
3. 過去の議事録に関する質問に、複数回を横断して回答する
4. 未完了のアクションアイテムを追跡し、リマインドする
5. 繰り返し議論される未解決課題を検出する

制約:
- 分からない担当者や期限を推測しない
- 事実、決定事項、未決事項、仮定を分離する
- Discord 投稿に適した簡潔な Markdown を返す
"""


def build_root_agent(settings: Settings | None = None) -> Any:
    from google.adk import Agent

    actual_settings = settings or get_settings()
    from google.adk.tools.load_memory_tool import load_memory

    return Agent(
        model=actual_settings.gemini_model,
        name="minutes_agent",
        instruction=AGENT_INSTRUCTION,
        tools=[
            transcribe_audio,
            generate_minutes,
            extract_action_items,
            search_minutes,
            get_pending_actions,
            send_discord_message,
            load_memory,
        ],
    )


root_agent = build_root_agent()
