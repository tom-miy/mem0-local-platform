# MCP 境界

MCP サーバーは、エージェントアクセスのポリシー適用層です。

`mcp/server.py` が公開するツールは、mem0 に問い合わせる前に読み取り可能テナントの
絞り込みを適用します。MCP から mem0 への登録は行いません。

## ツール

- `search_memory`: 読み取り可能テナントを検索します。
- `related_repo_context`: リポジトリメタデータを考慮して検索します。
- `recent_project_memories`: プロジェクトに紐づく文脈を取得します。

## 読み取り境界

読み取り可能テナントは `mem0.policy.yml` に設定します。

```yaml
read:
  - mimr-tech
```

登録は GitHub Actions または Python CLI から行います。
AI エージェントの一時的な推測を MCP 経由で永続化しないためです。
