# ADR-0002: Discord アプリを録音 Bot 用と Interactions 用に分離する

| 項目 | 内容 |
|---|---|
| ステータス | Accepted |
| 日付 | 2026-07-09 |
| 決定者 | hinapupil（MiyaIF の提案を採用） |

## Context

design.md §5.2 は当初、単一の Discord アプリで「GCE Bot の Gateway 接続（`/join` `/stop` の voice 録音）」と「Cloud Run の Interactions Endpoint（`/ask` 等の HTTP 応答）」を併用する前提だった。

しかし Discord の仕様上、**アプリに Interactions Endpoint URL を設定すると、そのアプリの全インタラクション（スラッシュコマンド含む）は Gateway ではなくその URL に POST される**。つまり同一アプリ内で「一部コマンドは Gateway、一部は HTTP」という振り分けは不可能で、Endpoint を登録した瞬間に `/join` `/stop` が Bot に届かなくなり録音機能が壊れる（[issue #11](https://github.com/hinapupil/minutes-agent/issues/11)）。

選択肢:

- **案A（Endpoint 不使用）**: Interactions Endpoint URL を登録せず、全6コマンドを Gateway 経由で処理する。Bot 側 Cog に全コマンドが実装済みのため機能は完全に動く。「デプロイ済み URL」要件は Cloud Run の実在（`/health`、Cloud Tasks/Scheduler からの実呼び出し）で満たす
- **案B（Endpoint 登録 + 録音コマンド無効化）**: `/join` `/stop` が実質使えなくなるため採用不可
- **案C（2アプリ分離）**: 録音 Bot 用アプリ（Gateway）と Interactions 用アプリ（HTTP）に分離する。design.md が意図した「GCE Bot が落ちていても対話コマンドは動く」という可用性分離を実際に成立させる

締切直前だったこともあり、レビュー時点での Claude の推奨は案A（作業量最小）だった。

## Decision

**案C（2アプリ分離）を採用する。** プロジェクトオーナーが「設計のうまさを優先したい」と明示し、作業量よりアーキテクチャの正しさを選んだ（提出締切が 7/12 に延長され時間的余裕ができたことも追い風）。

| アプリ | application_id | 責務 |
|---|---|---|
| `minutes-bot`（録音 Bot 用） | `1482711695758463088` | `/join` `/stop` を Gateway で処理。voice 録音。**Interactions Endpoint URL は設定しない** |
| `minutes-interactions`（対話用） | `1524735297114603591` | `/minutes` `/ask` `/actions` `/action-done` を Cloud Run `/interactions` で処理。Gateway 接続なし・Bot 招待不要（`applications.commands` スコープのみ） |

- コマンド登録: 録音 Bot 側は Pycord が起動時に自動同期。Interactions 側は `python -m minutes_agent.discord_commands`（PR #12 で追加）で登録する
- Cloud Run の interactions サービスは `minutes-interactions` の public_key で署名検証する必要があるため、Terraform 変数を録音 Bot 用と分離する（`interactions_discord_application_id` / `interactions_discord_public_key`）

## Consequences

**得られるもの:**
- design.md §5.2 の可用性分離（GCE Bot 停止時も対話コマンドが動く）が名実ともに成立する
- 「デプロイ済み URL」が審査時に実際にインタラクションを受ける生きたエンドポイントになる
- 録音機能とテキスト対話機能の障害ドメインが分離される

**失うもの / リスク:**
- Discord アプリ・トークン・公開鍵の管理対象が2倍になる（tfvars の変数分離、シークレット追加）
- ユーザーから見えるアプリが2つになる（コマンド一覧で `minutes-bot` と `minutes-interactions` が別々に見える）
- コマンド登録経路が2系統になる（自動同期 + CLI）

**不可逆性:**
- 低い。案A に戻す場合は minutes-interactions のギルド認可を解除し、Endpoint URL を外し、Bot 側 Cog の全コマンド自動同期に任せるだけ

## 関連

- [issue #11](https://github.com/hinapupil/minutes-agent/issues/11)（問題の発見と決定の記録）
- PR #12（Interactions 用コマンド登録 CLI と分離方針ドキュメント、MiyaIF）
- [Runbook: Discord 設定](../runbooks/discord-setup.md)（実施記録）
- [[0001-devbox-for-dev-and-prod-environment]]
