# Discord サーバー・アプリケーション設定 — Runbook

Design Doc: [docs/design.md](../design.md) ／ 関連 issue: [#7](https://github.com/hinapupil/minutes-agent/issues/7), [#10](https://github.com/hinapupil/minutes-agent/issues/10), [#11](https://github.com/hinapupil/minutes-agent/issues/11)

デモ用 Discord サーバーの作成と、Bot アプリケーションの作成・設定の手順。Terraform（`infra/terraform.tfvars`）が必要とする値の取得までを扱う。

> [!NOTE]
> ここで得る値の扱い区分:
>
> | 値 | 秘密度 | 行き先 |
> |---|---|---|
> | `application_id` | 公開情報 | `terraform.tfvars` |
> | `public_key` | 公開情報（署名検証用の公開鍵） | `terraform.tfvars` |
> | `channel_id` | 公開情報 | `terraform.tfvars` |
> | Bot token | **秘密** | Secret Manager（`just secret-set discord-bot-token`） |
> | Webhook URL | **秘密** | Secret Manager（`just secret-set discord-webhook-url`） |
>
> 秘密の2つはチャット・issue・git に絶対に貼らない。

---

## Phase 1: デモ専用サーバーの作成（2分）

既存の私用・チームサーバーを使わない。理由: (1) デモ動画（issue #8）に無関係なチャンネル名・個人情報が写り込む、(2) E2E テスト中の Bot の誤投稿が実チャンネルを汚す。

**手順（Discord クライアント or https://discord.com/app）:**
- [ ] 左サイドバー最下部の「+」→「オリジナルの作成」→「自分と友達のため」→ サーバー名を入力（例: `minutes-agent-demo`）
- [ ] デフォルトで `general`（テキスト）と `General`（ボイス）チャンネルが作られることを確認
- [ ] メンバーを招待: サーバー名右クリック → 「友達を招待」→ 招待リンクを MiyaIF に共有

**確認:**
- [ ] テキストチャンネル 1（議事録投稿先）、ボイスチャンネル 1（録音対象）が存在する

## Phase 2: アプリケーションの作成（3分）

**手順（https://discord.com/developers/applications）:**
- [ ] 右上「New Application」→ 名前を入力（例: `Minutes Agent`）→ 利用規約に同意して作成
- [ ] **General Information** ページで以下をコピーし、`infra/terraform.tfvars` 用に控える:
  - [ ] `APPLICATION ID` → `discord_application_id`
  - [ ] `PUBLIC KEY` → `discord_public_key`

> [!WARNING]
> **Interactions Endpoint URL は設定しない**（issue #11 の決定まで）。設定すると Discord は全スラッシュコマンドを Gateway ではなくその URL に送るため、`/join` `/stop` が GCE Bot に届かず録音機能が壊れる。全コマンドは Bot の Gateway 接続経由で動く（Bot 側 Cog に 6 コマンドすべて実装済み）。

## Phase 3: Bot の設定（3分）

**手順（左メニュー「Bot」）:**
- [ ] 「Reset Token」→ 表示されたトークンをコピー（**この画面を閉じると二度と見えない**。漏れたら再度 Reset でローテーション可能）
- [ ] トークンを Secret Manager へ投入（シェル履歴に残さないため隠しプロンプト経由）:
  ```bash
  just secret-set discord-bot-token
  ```
- [ ] **Privileged Gateway Intents** で以下を ON にして Save:
  - [ ] `SERVER MEMBERS INTENT` — `bot/main.py` の `intents.members = True` に対応
  - [ ] `MESSAGE CONTENT INTENT` — 会議中テキスト発言の収集用（コード側の対応は issue #10）
- [ ] `PUBLIC BOT` は OFF にする（デモ用のため誰でも招待できる必要はない）

> [!NOTE]
> Privileged Intents は 100 サーバー未満の Bot ならトグルだけで有効化でき、Discord の審査は不要。

## Phase 4: Bot をサーバーに招待（2分）

**手順（左メニュー「OAuth2」→「URL Generator」）:**
- [ ] Scopes: `bot` と `applications.commands` の 2 つにチェック
- [ ] Bot Permissions: `View Channels` / `Send Messages` / `Embed Links` / `Connect` / `Speak` / `Use Voice Activity`
- [ ] 生成された URL をブラウザで開き、Phase 1 のサーバーを選択して認証
- [ ] サーバーのメンバー一覧に Bot（オフライン状態）が表示されることを確認

## Phase 5: チャンネル ID と Webhook の取得（3分）

**手順:**
- [ ] Discord クライアントで開発者モードを ON: ユーザー設定 → 詳細設定 → 開発者モード
- [ ] 議事録投稿先テキストチャンネルを右クリック → 「チャンネルIDをコピー」→ `discord_channel_id` として控える
- [ ] 同チャンネルの設定（歯車）→ 連携サービス → ウェブフック → 「新しいウェブフック」→ 名前を設定（例: `Minutes Agent`）→ 「ウェブフックURLをコピー」
- [ ] Webhook URL を Secret Manager へ投入:
  ```bash
  just secret-set discord-webhook-url
  ```

## Phase 6: 後続作業への引き渡し

- [ ] `agent-api-token` を自動生成・投入（未実施なら）: `just secret-gen-agent-token`
- [ ] `gcloud secrets list --project=minutes-agent-hackathon` で 3 シークレット（`discord-bot-token` / `discord-webhook-url` / `agent-api-token`）の存在を確認
- [ ] `infra/terraform.tfvars` に公開値 3 つ（`discord_application_id` / `discord_public_key` / `discord_channel_id`）を反映 → [Runbook: GCP ブートストラップ Phase 6](gcp-bootstrap.md) と issue #4 へ続く

---

## 実施記録（2026-07-09、ブラウザ自動操作で実施）

新規作成の代わりに、**既存アプリ `minutes-bot` を再利用**した（Developer Portal に本プロジェクト用として作成済みのアプリが存在したため。Phase 2 の「New Application」はスキップ）。

| 項目 | 値・状態 |
|---|---|
| アプリ | `minutes-bot`（既存を再利用） |
| `discord_application_id` | `1482711695758463088` |
| `discord_public_key` | `0f678a2e2c4ce7874f2e062ae5572d6da63345bfafb4b41111b29c7c468ce3cc` |
| 特権 Intents | 3つとも既に ON だった（Server Members / Message Content / Presence）→ Phase 3 のトグル作業は不要だった |
| Interactions Endpoint URL | 未設定のまま（issue #11 案A どおり） |
| サーバー | `minutes-agent-demo` を新規作成（guild_id: `1524716458670817382`） |
| `discord_channel_id`（#一般） | `1524716459106897980` |
| Bot 招待 | 完了（scopes: bot + applications.commands、権限6種） |
| Webhook | `#一般` に `Minutes Agent` 名で作成済み（URL の Secret Manager 投入は下記残作業） |
| MiyaIF 招待リンク | `https://discord.gg/tkZ9uBhDE`（30日有効） |

**追記（同日）: 2アプリ分離（[ADR-0002](../adr/0002-split-discord-apps-for-gateway-and-interactions.md)）に伴う Interactions 用アプリの作成:**

| 項目 | 値・状態 |
|---|---|
| アプリ | `minutes-interactions`（新規作成。作成時に hCaptcha が出るため人間の操作が必要だった） |
| `interactions_discord_application_id` | `1524735297114603591` |
| `interactions_discord_public_key` | `da54897b79b8693e8c0f9df2fda9e3794b2ad5a1557f35ef3113bc3989ceb315` |
| ギルド認可 | `applications.commands` スコープのみでデモサーバーに認可済み（Gateway 接続しないため Bot 招待・Intents 不要） |
| Interactions Endpoint URL | **未設定**。Cloud Run デプロイ後に `terraform output -raw discord_interactions_url` の値を設定する（PING 検証あり） |
| コマンド登録 | デプロイ後に `python -m minutes_agent.discord_commands --guild-id 1524716458670817382` で登録（このアプリの Bot トークンが必要 → リセットして `just secret-set discord-interactions-bot-token`） |

> [!NOTE]
> 録音 Bot 用 `minutes-bot` には Interactions Endpoint URL を**設定しない**（設定すると `/join` `/stop` が Gateway に届かなくなる）。詳細な分離方針は [docs/discord-setup.md](../discord-setup.md)（PR #12、MiyaIF）と ADR-0002 を参照。

**残作業（秘密情報のためユーザー本人が実施）:**
- [ ] Bot トークンのリセットと投入: Portal の Bot ページで「トークンをリセット」→ `just secret-set discord-bot-token`
  - 既存トークンは無効化される。このアプリは別サーバーに1件インストール済みのため、もし旧トークンで動いているプロセスがあれば止まる点に注意
- [ ] Webhook URL の投入: `#一般` チャンネル設定 → 連携サービス → `Minutes Agent` → 「ウェブフックURLをコピー」→ `just secret-set discord-webhook-url`
- [ ] `just secret-gen-agent-token`（未実施なら）
- [ ] 招待リンクを MiyaIF に送付

## ロールバック手順

- Bot token が漏れた: Developer Portal → Bot → 「Reset Token」で即ローテーション → `just secret-set discord-bot-token` で新値を投入（GCE Bot は次回再起動時に新トークンを読む）
- Webhook URL が漏れた: チャンネル設定 → 連携サービス → 該当 Webhook を削除 → 新規作成 → `just secret-set discord-webhook-url`
- アプリごと作り直す: Developer Portal → General Information 最下部 → Delete App（`application_id` / `public_key` が変わるため `terraform.tfvars` の更新と再 apply が必要）
- サーバー削除: サーバー設定 → サーバーを削除（デモ用なので影響なし）

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| Bot 起動時に `PrivilegedIntentsRequired` で落ちる | コードが要求する特権 Intent（members / message_content）が Portal で OFF | Phase 3 のトグルを ON にして Bot を再起動 |
| スラッシュコマンドがサーバーに出てこない | `applications.commands` スコープなしで招待した | Phase 4 の URL（両スコープ入り）で再招待。反映に最大1時間かかることがある（グローバルコマンド） |
| `/join` しても「Unsupported command」が返る | Interactions Endpoint URL が設定されている（issue #11 の問題） | General Information の Interactions Endpoint URL を空にして Save |
| テキスト発言が議事録に入らない（content が空） | MESSAGE CONTENT INTENT が OFF、またはコード側 `intents.message_content` 未設定 | Phase 3 のトグル + issue #10 の修正の両方が必要 |

## 再実行時に変更すべきパラメータ

| パラメータ | 本書での値 | 備考 |
|---|---|---|
| サーバー名 | `minutes-agent-demo` | 任意 |
| アプリ名 | `Minutes Agent` | 任意（ユーザーに見える Bot 名） |
| GCP プロジェクト | `minutes-agent-hackathon` | `justfile` の `gcp_project` 変数 |
