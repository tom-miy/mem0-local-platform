# 検証

ローカル検証では、実際の mem0 サービスを必須にせず、索引作成の流れを確認します。

構文チェックを実行します。

```bash
mise run compile
```

dry-run モードで取り込みを実行します。

```bash
mise run ingest-dry-run
```

リポジトリ同期のパスルールを include/exclude に変換します。

```bash
mise run sync-path-rules
```

mem0 が起動している場合は、`--dry-run` を外すとチャンクを更新または追加できます。

Compose 実行環境では、compose ネットワーク内でヘルスチェックを確認できます。

```bash
docker compose -f compose.yml exec mem0 \
  uv run python -c "import httpx; print(httpx.get('http://localhost:8000/healthz').json())"
```

compose ネットワークの外から接続する場合は、Cloudflare で保護された mem0 ホスト名を
使います。

ローカルチェックをすべて実行します。

```bash
mise run check
```

`data/` 以外のローカル検証生成物を削除します。

```bash
mise run clean
```

`clean` は `.cache` と Python の `__pycache__` ディレクトリを削除します。
`data/` は削除しません。

Compose や結合テストで作成したデータを削除します。

```bash
mise run clean-data
```

`.venv` と `data/` を含む、ローカル生成状態をすべて削除します。

```bash
mise run clean-all
```
