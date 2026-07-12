# ruff: noqa: E501  — SVG 断片の f-string は分割すると可読性が落ちるため行長制限を除外
"""システム構成図の生成スクリプト。

アイコンは iconify の `gcp` コレクション（Google Cloud Icons, Apache 2.0）と
`logos` コレクション（CC0）から取得したものを icons/ に同梱している。
再生成: python3 generate_architecture.py → architecture.svg
"""
import pathlib
import re

BASE = pathlib.Path(__file__).parent
GCP_BLUE = "#4285F4"
BLURPLE = "#5865F2"
INK = "#202124"
SUB = "#5f6368"
LINE = "#80868b"


def icon_inline(name: str, x: float, y: float, size: int = 40) -> str:
    raw = (BASE / f"icons/{name}.svg").read_text()
    vb = re.search(r'viewBox="([^"]+)"', raw).group(1)
    inner = re.sub(r"^<svg[^>]*>|</svg>$", "", raw.strip())
    return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="{vb}">{inner}</svg>'


def card(x, y, w, h, title, sub, icon):
    ic = icon_inline(icon, x + 16, y + (h - 40) / 2, 40)
    return f'''
  <g filter="url(#shadow)">
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="white" stroke="#dadce0"/>
    {ic}
    <text x="{x+70}" y="{y+h/2-4}" font-size="16" font-weight="bold" fill="{INK}">{title}</text>
    <text x="{x+70}" y="{y+h/2+18}" font-size="12" fill="{SUB}">{sub}</text>
  </g>'''


def label(lx, ly, text):
    return (
        f'<rect x="{lx-len(text)*4.1-8}" y="{ly-13}" width="{len(text)*8.2+16}" height="20" rx="10" fill="#e8f0fe"/>'
        f'<text x="{lx}" y="{ly+2}" text-anchor="middle" font-size="12" fill="#1967d2">{text}</text>'
    )


def arrow(x1, y1, x2, y2, ltext="", lx=None, ly=None):
    lx = lx if lx is not None else (x1 + x2) / 2
    ly = ly if ly is not None else (y1 + y2) / 2 - 4
    s = f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" stroke-width="2.2" marker-end="url(#arr)"/>'
    if ltext:
        s += "\n  " + label(lx, ly, ltext)
    return s


def path_arrow(points, ltext="", lx=0, ly=0):
    d = "M " + " L ".join(f"{x} {y}" for x, y in points)
    s = f'  <path d="{d}" fill="none" stroke="{LINE}" stroke-width="2.2" marker-end="url(#arr)"/>'
    if ltext:
        s += "\n  " + label(lx, ly, ltext)
    return s


svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1480 800" font-family="'Hiragino Sans','Noto Sans JP',sans-serif">
  <defs>
    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="{LINE}"/>
    </marker>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#000" flood-opacity="0.10"/>
    </filter>
  </defs>
  <rect width="1480" height="800" fill="white"/>
  <text x="740" y="36" text-anchor="middle" font-size="21" font-weight="bold" fill="{INK}">Minutes Agent — システム構成</text>

  <!-- Discord -->
  <rect x="30" y="70" width="310" height="690" rx="16" fill="#f5f6ff" stroke="{BLURPLE}" stroke-width="2"/>
  {icon_inline("discord", 110, 90, 30)}
  <text x="200" y="112" text-anchor="middle" font-size="18" font-weight="bold" fill="{BLURPLE}">Discord</text>
  {card(60, 150, 250, 76, "ユーザー", "会議の参加者たち", "discord")}
  {card(60, 340, 250, 76, "ボイスチャンネル", "会議の場（E2EE/DAVE 対応）", "discord")}
  {card(60, 600, 250, 76, "#議事録 チャンネル", "議事録・リマインドが届く", "discord")}

  <!-- Google Cloud -->
  <rect x="390" y="70" width="1060" height="690" rx="16" fill="#f8f9fa" stroke="{GCP_BLUE}" stroke-width="2"/>
  <text x="920" y="106" text-anchor="middle" font-size="18" font-weight="bold" fill="{GCP_BLUE}">Google Cloud</text>

  {card(430, 150, 280, 76, "Compute Engine", "Pycord Bot（Gateway / 録音）", "compute-engine")}
  {card(430, 340, 280, 76, "Cloud Tasks", "非同期ジョブキュー", "cloud-tasks")}
  {card(430, 450, 280, 76, "Cloud Scheduler", "毎朝の自律リマインド起点", "cloud-scheduler")}

  <rect x="760" y="150" width="340" height="430" rx="14" fill="white" stroke="#dadce0" stroke-width="2"/>
  {icon_inline("cloud-run", 850, 168, 26)}
  <text x="950" y="187" text-anchor="middle" font-size="15" font-weight="bold" fill="{SUB}">Cloud Run</text>
  {card(790, 210, 280, 70, "Interactions API", "スラッシュコマンド応答（公開）", "cloud-run")}
  {card(790, 320, 280, 70, "Agent API", "議事録パイプライン（内部）", "cloud-run")}
  {card(790, 470, 280, 84, "ADK Agent", "Gemini 3.5 Flash・自律判断", "vertexai")}

  {card(1150, 210, 270, 70, "Speech-to-Text", "話者別の文字起こし", "speech-to-text")}
  {card(1150, 320, 270, 70, "Gemini API", "議事録生成・用語補正", "vertexai")}
  {card(1150, 500, 270, 70, "Cloud Storage", "録音 wav（30日で削除）", "cloud-storage")}
  {card(1150, 610, 270, 70, "Firestore", "議事録 / 宿題 / 用語集 / メモリ", "firestore")}

  {arrow(310, 175, 430, 182, "/join /stop", 372, 156)}
  {arrow(310, 375, 430, 372, "録音（話者別）", 370, 356)}
  {path_arrow([(310, 215), (360, 215), (360, 292), (745, 292), (745, 250), (790, 250)], "/ask /actions /setup", 470, 280)}
  {arrow(570, 226, 570, 340, "enqueue", 615, 316)}
  {arrow(710, 375, 790, 358, "HTTP", 752, 350)}
  {arrow(710, 485, 800, 380, "HTTP", 748, 452)}
  {arrow(930, 390, 930, 470)}
  {arrow(1070, 245, 1150, 245)}
  {arrow(1070, 355, 1150, 355)}
  {arrow(1070, 505, 1150, 528, "音声取得", 1108, 498)}
  {arrow(1070, 530, 1150, 638, "read / write", 1092, 596)}
  {arrow(790, 530, 310, 640, "Webhook で自動投稿", 540, 596)}
</svg>'''

(BASE / "architecture.svg").write_text(svg)
print("architecture.svg written")
