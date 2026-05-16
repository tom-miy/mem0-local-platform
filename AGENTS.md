# AGENTS.md

- 既存コードの設計意図を尊重する
- 不要なリファクタリングをしない
- 変更理由を明確に説明する
- 不明点は推測せず確認する
- 破壊的変更前に影響範囲を説明する
- テスト可能な変更を優先する
- Go/Rustでは型安全性と明示性を重視する
- README/AGENTS.md を最初に読む
- 指示がない限り secrets/.env を読まない
- 変更は small-batch を優先する
- 1コミット = 1責務 を基本とする
- 大規模変更は先に分割案を提示する
- 構造変更時は rollback 方法を説明する
- 生成コードより reviewability を優先する
- ログは structured logging を優先する
- 個人情報・秘密情報をログ出力しない
- 既存 README / ADR / docs と整合性を取る
- docs/testing, docs/architecture を参照する
- 推測で TODO を削除しない
- 使われていない abstraction を追加しない
- 変更時は observability 影響も確認する

