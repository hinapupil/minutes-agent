# Architecture Decision Records

このディレクトリには、minutes-agent の設計上の意思決定を Nygard 形式の ADR として記録する。

## 命名規則

`NNNN-kebab-case-title.md`（例: `0001-use-gcs-backend-for-terraform-state.md`）。連番は採用日時系列。

## 書くタイミング

- 複数の妥当な選択肢があり、どれかを選んだ理由を将来読み返す必要がある判断
- 一度決めたら覆すコストが高い判断（アーキテクチャ、データストア、認証方式など）
- 議論が割れた、または当初の推奨と異なる選択をした判断

軽微な設定変更や明白なバグ修正には書かない。
