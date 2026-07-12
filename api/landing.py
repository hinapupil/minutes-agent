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
「決めたことが実行されない」という会議の課題を、エージェントの自律的な追跡で解決します。</p>

<p>DevOps × AI Agent Hackathon (Findy × Google Cloud) 提出作品。</p>

<h2>🔍 審査員のかたへ — 動作確認の手順（約3分）</h2>
<ol>
  <li>この URL が開けている時点で Cloud Run 上の Agent API は稼働中です
      （このサービスが Discord からのインタラクションを署名検証して処理しています）</li>
  <li><a href="https://discord.gg/tkZ9uBhDE">デモ Discord サーバーに参加</a>
      （お手持ちの Discord アカウントでどうぞ）</li>
  <li>任意のチャンネルで <code>/ask 最近なにを決めた？</code> を実行 —
      ADK Agent が過去議事録を自律検索して回答します</li>
  <li><code>/setup repo:&lt;owner/repo&gt;</code> — お好きな public リポジトリを指定すると、
      エージェントが README・docs・コントリビューターを読んで議事録用の用語集を学習します
      （音声認識の固有名詞補正に使われます）</li>
  <li><code>/actions</code> で抽出済みアクションアイテムの一覧、
      <code>/action-done &lt;id&gt;</code> で完了化を確認できます</li>
</ol>

<h3>録音 → 議事録のパイプラインを検証するには</h3>
<ul>
  <li><strong>本命: ライブ録音</strong> — ボイスチャンネルで <code>/join</code> →
      会話 → <code>/stop</code>。話者別に録音され、数分で <code>#議事録</code> に
      議事録・アクションアイテム・継続確認（前回決定事項との突き合わせ）が自動投稿されます。
      会話相手が必要なため、お一人の場合はデモ動画でご確認ください</li>
  <li><strong>お一人でも試せる手動経路</strong> — <code>/minutes</code> に音声ファイル
      （wav / mp3 / m4a / flac / ogg、zip も可）を添付すると、同じ
      Cloud Tasks → Speech-to-Text → Gemini のパイプラインが走ります</li>
</ul>
<p>毎日 10:00 (JST) には Cloud Scheduler 起点でエージェントが未完了アクションを
自律判定し、期限切れ・期限間近のものをリマインド投稿します（between-meetings の自律動作）。</p>

<h2>🧭 なぜ「デモサーバー招待」方式か</h2>
<p>通常の Discord bot は、利用者が自分のサーバーにインストールして使います。
しかし本プロダクトの中心機能は「<strong>複数人の音声会議を録音して議事録にする</strong>」ことなので、
お一人でインストールしても肝心の会議を体験できません。</p>
<p>そこで審査用には、実際の会議の録音・議事録・アクションアイテムが
すでに入った<strong>デモサーバー</strong>をご用意しました。参加すればすぐに
<code>/ask</code> や <code>/actions</code> で「過去の会議が蓄積されたサーバー」を
そのまま体験できます
（この判断の記録: <a href="https://github.com/hinapupil/minutes-agent/blob/main/docs/adr/0004-demo-server-as-judge-verification-path.md">ADR-0004</a>）。</p>
<p>内部はサーバー（ギルド）単位の設定で設計してあり、一般公開（インストール型）への
移行は議事録の投稿先まわりの切り替えのみで、ロードマップとして管理しています
（<a href="https://github.com/hinapupil/minutes-agent/issues/57">#57</a>）。</p>

<h2>🏗️ 構成（すべて Google Cloud）</h2>
<p>GCE (Pycord Bot / voice録音) → Cloud Storage → Cloud Tasks →
<strong>Cloud Run (FastAPI + ADK Agent)</strong> → Speech-to-Text / Gemini →
Firestore → Discord Webhook。IaC は Terraform、CI/CD は GitHub Actions
(WIF keyless 認証・gitleaks / pip-audit / Checkov / CodeQL 付き)。</p>

<h2>🔗 リンク</h2>
<p>
  <a class="btn" href="https://github.com/hinapupil/minutes-agent">GitHub リポジトリ</a>
  <a class="btn"
     href="https://github.com/hinapupil/minutes-agent/blob/main/docs/design.md">設計文書
     (design.md)</a>
  <a class="btn" href="https://protopedia.net/">Proto Pedia 作品ページ</a>
  <a class="btn" href="https://discord.gg/tkZ9uBhDE">デモサーバー招待</a>
</p>

<footer>Minutes Agent — DevOps × AI Agent Hackathon 2026 /
録音データは30日で自動削除されます。デモサーバーでの発言・音声は
デモ目的で処理されることに同意の上ご参加ください。</footer>
</body>
</html>"""
