from __future__ import annotations

from agent.tools.gemini_client import GeminiTextClient
from minutes_agent.config import Settings

MINUTES_PROMPT_TEMPLATE = """\
あなたは Discord 会議の議事録を作る AI エージェントです。
目的は、決定事項と実行責任を曖昧にしないことです。

制約:
- 日本語で書く
- 推測で担当者や期限を補完しない
- 不明な担当者は「担当者未設定」と書く
- 不明な期限は「期限未設定」と書く
- 決定事項、未決事項、Action Items を分離する
- テキスト参加者の発言が含まれていれば本文に反映する
- 同じ議題が過去文脈にあれば「継続議題」として明示する

出力形式:
# 議事録
## 概要
## 決定事項
## 未決事項
## 論点
## Action Items
## 継続確認

過去文脈:
{context}

今回の文字起こし:
{transcript}
"""


class GeminiMinutesGenerator:
    def __init__(self, settings: Settings) -> None:
        self._client = GeminiTextClient(settings)

    def generate(self, transcript: str, context: str = "") -> str:
        if not transcript.strip():
            raise ValueError("transcript must not be empty")
        prompt = MINUTES_PROMPT_TEMPLATE.format(
            transcript=transcript.strip(),
            context=context.strip() or "なし",
        )
        return self._client.generate(prompt)

