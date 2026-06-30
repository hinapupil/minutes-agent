# ADR-0001: 開発環境・本番ビルド環境を Devbox（Nix）に統一する

| 項目 | 内容 |
|---|---|
| ステータス | Accepted |
| 日付 | 2026-07-01 |
| 決定者 | hinapupil |

## Context

minutes-agent はハッカソン用2人チームプロジェクト（[DevOps × AI Agent Hackathon](https://findy.co.jp/4127/)、提出期限 2026-07-10）で、開発者の OS が Windows と macOS に分かれている。既存の `README.md` の「Local Development」手順は PowerShell 専用（Windows 想定）で書かれており、macOS/zsh 環境ではそのまま使えないという実害があった。

[hinapupil/project-template](https://github.com/hinapupil/project-template) の知見導入を検討する中で、開発環境の再現性を高める選択肢として Devbox（Nix ベースの再現可能な開発環境ツール）の導入が俎上に載った。

選択肢:
- **Option A（開発環境層のみ）**: Lefthook + gitleaks + justfile のみ導入し、Devbox（Nix ベース）は見送る。既存の Python venv + pip + Docker ベースのワークフローは変更しない
- **Option B（開発環境 + 将来的に本番ビルドも統一）**: Devbox（`devbox.json`）を導入し、`python312`/`ffmpeg`/`libopus`/`just`/`lefthook`/`gitleaks` を管理する。将来的には本番ビルド（`Dockerfile`/`Dockerfile.bot`）も `devbox generate dockerfile` で生成する形に統一し、dev/prod を同型化する

Claude は当初 Option A を推奨した。理由は、ハッカソンの短納期（2026-07-10 提出）で Devbox 導入による CI 作り直しコスト・二重環境管理コストが見合わないという判断だった。また「本番ビルド経路（Dockerfile/Dockerfile.bot/deploy.yml）は Devbox 化しない」という前提を当初の境界線として置いていたが、これは Web 検索で確認した結果、技術的なベストプラクティスではなく単なる時間的制約からの判断だったことが判明した。Devbox は `devbox generate dockerfile` によって開発環境と同一の `devbox.json` から本番用 Dockerfile を生成する機能を公式に提供しており、dev/prod の環境を同型化することをむしろ推奨している（Jetify Cloud という `devbox.json` から直接デプロイするサービスも存在する）。

## Decision

**Option B** を採用する。

プロジェクトオーナーは Option A の推奨を明示的に覆し、「Windows でも macOS でも同一に動く開発環境にしたい」というクロスプラットフォーム再現性を本質的な要求として優先した。さらに、時間制約を理由にスコープを絞ることを拒否し「Devbox に統一したい（時間は考えなくていい）」と明言した。

ただし実行順序には制約がある。本番ビルド対象ファイル（`Dockerfile`/`Dockerfile.bot`/`deploy.yml`）は本 ADR 作成時点で `main` に存在せず、PR #1（`codex/app-complete-implementation`、"Bot/API/Agent実装とインフラ定義を追加"）にのみ存在する。PR #1 はまだ `CHANGES_REQUESTED` でマージされていない。そのため:

1. **今回（PR #2: `feat/devbox-just-lefthook`）のスコープ**: 開発環境層（`devbox.json`/`.envrc`/`justfile`/`lefthook.yml`）のみ
2. **本番ビルドの Devbox 統一**: PR #1 マージ後のフォローアップ PR として実施する

## Consequences

**得られるもの:**
- macOS/Windows で同一バージョンの `python312`/`ffmpeg`/`libopus` が再現される
- `direnv allow` だけで環境構築が完結し、PowerShell 専用手順への依存がなくなる
- 将来的に本番ビルドも同じ `devbox.json` から生成されることで、"works on my machine" 由来の dev/prod 差分が構造的になくなる

**現時点（本 ADR 作成時点）でまだ実現していないもの:**
- CI（`.github/workflows/ci.yml`）への devbox 組み込み: PR #1 が同じパスに新規ファイルを追加するため衝突を避けて今回は見送り、PR #1 マージ後にフォローアップする
- 本番ビルド（`Dockerfile`/`Dockerfile.bot`/`deploy.yml`）の Devbox 統一: 対象ファイルが PR #1 未マージのため着手不可、PR #1 マージ後のフォローアップ PR で実施する
- devbox 自体の依存解決の実検証: `devbox.json` に書いたパッケージ名（`python312`/`ffmpeg`/`libopus`）は search.devbox.sh で個別に存在確認したのみで、`devbox shell` での実解決はこの ADR 作成時点では未検証

**失うもの / リスク:**
- Nix ベースの Devbox は、Python venv + pip という既存のシンプルな構成に比べて学習コスト・デバッグ時の特殊性がある（Nix store のパス解決等）
- 2人チームのうち Devbox に不慣れなメンバーがいる場合、オンボーディングの初期コストが発生する

**不可逆性:**
- 低い。`devbox.json`/`.envrc`/`justfile`/`lefthook.yml` を削除し既存の venv 手順に戻すだけで撤回できる。本番ビルドを Devbox 化した後の撤回はやや手間が増えるが、`Dockerfile` を pip ベースの記述に戻せば同様に可能

## Sources

- [devbox.json Reference - Jetify Docs](https://www.jetify.com/docs/devbox/configuration)
- [Docker and Dev Containers | jetify-com/devbox | DeepWiki](https://deepwiki.com/jetify-com/devbox/4.3-docker-and-dev-containers)
- [Jetify Deploys: Automate your Backend Deployments](https://www.jetify.com/deploy)

## 関連

- PR #2: `feat/devbox-just-lefthook`（本 ADR の対象スコープ）
- PR #1: `codex/app-complete-implementation`（本番ビルド統一のフォローアップが依存するブランチ、未マージ）
- [Runbook: GCP インフラ ブートストラップ](../runbooks/gcp-bootstrap.md)
