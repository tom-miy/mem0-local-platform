# テナント境界

テナントはメモリアクセスの分離境界です。

リポジトリごとにテナントを作ってはいけません。
不要に運用対象が増え、ポリシーレビューも難しくなります。

推奨するテナント例:

- `secret-knowledge`
- `client-upwork-18384728-acme`
- `client-acme`

リポジトリで絞り込みたい場合はメタデータを使います。

```json
{
  "tenant": "secret-knowledge",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md"
}
```

MCP サーバーは、設定された読み取り境界の外にあるテナントが要求された場合、
その要求を拒否しなければなりません。
