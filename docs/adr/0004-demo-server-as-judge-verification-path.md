# ADR-0004: 審査員の検証導線はデモサーバー招待方式とする

| 項目 | 内容 |
|---|---|
| ステータス | Accepted |
| 日付 | 2026-07-12 |
| 決定者 | hinapupil（grill-with-docs セッションで確定） |

## Context

ハッカソン提出要件に「審査員が検証できるデプロイ済み URL」がある。Discord bot の標準的な配布形態は「利用者が OAuth2 install link で自分のサーバーに bot を追加する」方式（bot インストール型）であり、「デモサーバーに審査員を招待する」現方式はプロダクトの完成度という点で見劣りしないか、という問題提起がプロジェクトオーナーからあった。

選択肢:

- **案A（デモサーバー招待を維持）**: 審査員は minutes-agent-demo サーバーに招待リンクで参加して検証する
- **案B（bot インストール型を今夜追加）**: OAuth2 install link を公開し、任意サーバーで動くようにする。議事録投稿先が webhook 1 本固定のため、`/setup` でのチャンネル指定 + webhook 自動作成の実装が必要（+2〜3時間 + 未検証面の増加）
- **案C（ハイブリッド）**: 導線は招待のまま、マルチギルド実装だけ完成させる

## Decision

**案A を採用する**（決定日 = 提出締切当日、残り約 9 時間の状況下。独立調査エージェントによる一次情報調査でも案A が推奨された）。

1. **製品固有の事情: 審査員は単独では core value を再現できない** — minutes-agent の価値は「複数話者の実会議 → AI 議事録」。審査員が自サーバーに bot を入れても、1人ではボイス会議が成立せず議事録の質を体験できない。データ仕込み済みデモサーバーは「実装できなかった逃げ」ではなく、確実に価値を見せる積極的な選択（録音 bot の実例 Craig は install 型だが、録音ファイルを返すだけで solo でも成立する点が違う）
2. **決定的な技術制約: 通知ランタイムに bot token が無い** — 議事録の最終投稿は Cloud Tasks 非同期のため interaction followup が使えず（token 15分失効）、固定 webhook で投稿している。マルチギルド化には「Cloud Run SA への bot token Secret アクセス付与 → Terraform 変更・再デプロイ → 投稿経路の差し替え → 新ギルドでの全ループ E2E」の連鎖が必要で、締切当日には見合わない
3. **中途半端なハイブリッドは有害** — 固定 webhook のまま OAuth2 install link だけ公開すると、審査員が本物の導線を試した際に誤チャンネル投稿・無反応になる。install link を出すなら投稿経路の修正とセットでなければならない
4. なお **public 化自体に Discord の審査は不要**（bot verification が必須になるのは 100 サーバー以上。voice 受信・slash command 運用に privileged intents も不要）。移行の障壁は審査ではなく上記 2 の設計変更であり、[#57](https://github.com/hinapupil/minutes-agent/issues/57) で行う。ギルド単位設計（`guild_settings/{guild_id}`、ADR-0003）と通知層の webhook オーバーライド引数（`minutes_agent/discord.py`）は布石として実装済み

一次情報: [Discord OAuth2 docs](https://docs.discord.com/developers/topics/oauth2) / [Webhook resource（`POST /channels/{id}/webhooks`）](https://docs.discord.com/developers/resources/webhook) / bot verification の閾値・挙動は Discord サポートコミュニティ告知に基づく。

ランディングページには「なぜデモサーバー方式か」と上記ロードマップを明記し、意図的な選択であることを審査員に伝える。

## Consequences

**得られるもの:**
- 審査体験の統制（データ仕込み済み・確実に動く環境）
- 締切当日の実装リスク回避

**失うもの / 引き受けるリスク:**
- 「そのまま自分のサーバーで使える」プロダクト感の訴求は動画・LP の説明に依存する
- デモサーバーの荒らし・誤操作リスク（招待リンクが公開されるため、チャンネル権限の整理が前提）
