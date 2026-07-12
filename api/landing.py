"""審査員・訪問者向けのランディングページ（GET /）。

「デプロイしたプロジェクトのURL（動作確認できる状態にしておくこと）」という
提出要件に応えるページ。本プロダクトの本体は Discord Bot のため、
素の URL では何も見えない問題をここで解決する。
"""

from __future__ import annotations

LANDING_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Minutes Agent — Discord 会議アカウンタビリティ・エージェント</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif;
         max-width: 760px; margin: 2rem auto; padding: 0 1.25rem; line-height: 1.7; }
  h1 { font-size: 1.6rem; } h2 { font-size: 1.15rem; margin-top: 2rem;
       border-bottom: 1px solid #8884; padding-bottom: .3rem; }
  .badge { display: inline-block; background: #22a55933; border: 1px solid #22a559;
           border-radius: 999px; padding: .1rem .7rem; font-size: .85rem; }
  ol li { margin: .4rem 0; }
  code { background: #8882; border-radius: 4px; padding: .1rem .35rem; }
  a.btn { display: inline-block; border: 1px solid #5865F2; border-radius: 8px;
          padding: .45rem 1rem; text-decoration: none; margin: .25rem .4rem .25rem 0; }
  footer { margin-top: 3rem; font-size: .8rem; opacity: .7; }
</style>
</head>
<body>
<h1>📝 Minutes Agent</h1>
<p><span class="badge">✅ このサービスは稼働中です</span>
   （<a href="/health">/health</a> でヘルスチェック応答を確認できます）</p>

<p>Discord の定例ミーティングを自動録音し、<strong>議事録生成・アクションアイテム抽出・
進捗リマインド</strong>までを自律実行する AI エージェントです。
「決めたことが実行されない」という会議の本質課題を、エージェントの自律的な追跡で解決します。</p>

<p>DevOps × AI Agent Hackathon (Findy × Google Cloud) 提出作品。</p>

<h2>🔍 審査員のかたへ — 動作確認の手順（約3分）</h2>
<ol>
  <li>この URL が開けている時点で Cloud Run 上の Agent API は稼働中です
      （このサービスが Discord からのインタラクションを署名検証して処理しています）</li>
  <li><a href="https://discord.gg/tkZ9uBhDE">デモ Discord サーバーに参加</a>
      （お手持ちの Discord アカウントでどうぞ）</li>
  <li>任意のチャンネルで <code>/ask 最近なにを決めた？</code> を実行 —
      ADK Agent が過去議事録を自律検索して回答します</li>
  <li><code>/minutes</code> に音声ファイル（wav / mp3 / m4a 等）を添付 —
      Cloud Tasks → Speech-to-Text → Gemini のパイプラインが走り、
      数分で <code>#議事録</code> チャンネルに議事録とアクションアイテムが投稿されます</li>
  <li><code>/actions</code> で抽出済みアクションアイテムの一覧、
      <code>/action-done &lt;id&gt;</code> で完了化を確認できます</li>
</ol>
<p>毎日 10:00 (JST) には Cloud Scheduler 起点でエージェントが未完了アクションを
自律判定し、期限切れ・期限間近のものをリマインド投稿します（between-meetings の自律動作）。</p>

<h2>🏗️ 構成（すべて Google Cloud）</h2>
<p>GCE (Pycord Bot / voice録音) → Cloud Storage → Cloud Tasks →
<strong>Cloud Run (FastAPI + ADK Agent)</strong> → Speech-to-Text / Gemini →
Firestore → Discord Webhook。IaC は Terraform、CI/CD は GitHub Actions
(WIF keyless 認証・gitleaks / pip-audit / Checkov / CodeQL 付き)。</p>

<h2>🔗 リンク</h2>
<p>
  <a class="btn" href="https://github.com/hinapupil/minutes-agent">GitHub リポジトリ</a>
  <a class="btn" href="https://protopedia.net/">Proto Pedia 作品ページ</a>
  <a class="btn" href="https://discord.gg/tkZ9uBhDE">デモサーバー招待</a>
</p>

<footer>Minutes Agent — DevOps × AI Agent Hackathon 2026 /
録音データは30日で自動削除されます。デモサーバーでの発言・音声は
デモ目的で処理されることに同意の上ご参加ください。</footer>
</body>
</html>"""
