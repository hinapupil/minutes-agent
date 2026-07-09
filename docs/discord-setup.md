# Discord Application Setup

## 前提

- Cloud Run のデプロイが完了している
- `terraform output -raw discord_interactions_url` で `/interactions` の公開URLを取得できる
- Discord Developer Portal でアプリ設定を変更できる権限がある
- Discord Bot Token と Webhook URL は Secret Manager に保存し、リポジトリへ保存しない

## 重要な制約

Discord のInteractions受信方式は次の2つから選択する

- Gateway connection
- HTTP via outgoing webhooks

Interactions Endpoint URL をDiscordアプリに設定した場合、そのアプリのInteractionsはHTTP webhookへ送られる。Pycord Bot がGatewayで `/join` / `/stop` を受ける構成とは同一アプリ内で両立しない

このプロジェクトでは次の分離を推奨する

- 録音Bot用Discordアプリ: `/join` / `/stop` をGatewayで処理
- Interactions用Discordアプリ: `/minutes` / `/ask` / `/actions` / `/action-done` をCloud Run `/interactions` で処理

録音デモを優先する場合は、録音Bot用DiscordアプリにはInteractions Endpoint URLを設定しない

## 設定手順

### 1. Interactions Endpoint URL の設定

1. `infra` でTerraform outputを確認

```powershell
terraform output -raw discord_interactions_url
```

2. Discord Developer Portal でInteractions用アプリを開く
3. General Information の Interactive Endpoint URL に出力値を設定
4. Save Changes を押し、Discord の PING 検証が成功することを確認

Cloud Run側は `api/interactions.py` で次を満たす

- PING payload `type: 1` に `{"type": 1}` を返す
- `X-Signature-Ed25519` と `X-Signature-Timestamp` を検証する

### 2. Interactions用スラッシュコマンド登録

テスト用ギルドへ即時反映したい場合

```powershell
$env:DISCORD_BOT_TOKEN = "<interactions-app-bot-token>"
$env:DISCORD_APPLICATION_ID = "<interactions-app-application-id>"
python -m minutes_agent.discord_commands --guild-id "<test-guild-id>"
```

グローバル登録する場合

```powershell
$env:DISCORD_BOT_TOKEN = "<interactions-app-bot-token>"
$env:DISCORD_APPLICATION_ID = "<interactions-app-application-id>"
python -m minutes_agent.discord_commands
```

登録対象

- `/minutes`
- `/ask`
- `/actions`
- `/action-done`

`/join` と `/stop` はInteractions用アプリには登録しない

### 3. 録音Botの招待

録音Bot用Discordアプリをテスト用ギルドに招待する

必要な権限

- View Channels
- Send Messages
- Use Slash Commands
- Connect
- Speak

Bot起動時にPycordがGateway用コマンドを同期する

- `/join`
- `/stop`

### 4. Webhook URL の共有

議事録投稿先チャンネルでWebhook URLを発行し、Secret Manager に保存する

```powershell
gcloud secrets versions add DISCORD_WEBHOOK_URL --data-file=webhook-url.txt
```

`webhook-url.txt` は作業後に削除し、コミットしない

## 確認項目

- Interactions用アプリのEndpoint URL保存時にPING検証が成功する
- `/ask` がCloud Runの `/interactions` 経由で応答する
- 録音Bot用アプリの `/join` がPycord Bot経由でVoice Channelへ参加する
- `/stop` 後にCloud Tasksへ議事録生成ジョブが登録される
- Webhookで議事録投稿先チャンネルへ投稿できる
