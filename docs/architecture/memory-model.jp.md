# メモリモデル

mem0 は、AI エージェントが開発中に文脈を検索するための基盤です。

長く残す知識は Git リポジトリ、Markdown ドキュメント、ADR、Obsidian ノートに
置きます。このプラットフォームは、それらを mem0 に索引して、開発中に
エージェントが必要な文脈を取得できるようにします。

## チャンク ID

チャンクは次の値から安定した更新 ID を作ります。

```text
repo:path:heading[:occurrence]
```

同じファイル内で同じ見出しが複数回出る場合だけ、末尾に occurrence を付けます。
現在の実装では、この値を SHA-256 でハッシュします。
同じワークフローを繰り返し実行しても冪等になり、同じ見出しの内容が更新された場合は
以前の索引内容を置き換えられます。

## メタデータ

各チャンクは次のようなメタデータを持ちます。

```json
{
  "tenant": "secret-knowledge",
  "repo": "mem0-local-platform",
  "path": "docs/architecture/memory-model.md",
  "type": "doc",
  "tags": ["mem0", "mcp"]
}
```

`tenant` は、AI エージェントが読んでよい知識の範囲を決めるために使います。
たとえば `secret-knowledge` だけを許可したエージェントは、`client-acme` の知識を
検索できません。

`repo` と `path` はアクセス制御ではありません。
検索結果を「どのリポジトリの、どのファイルから来た文脈か」として絞り込んだり、
表示したりするための情報です。

`type` は取り込み CLI が `path` から自動判定するファイル大分類です。
たとえば `docs/**` は `doc`、`adr/**` は `adr`、`.go` や `.py` は `code`、
`.yaml` や `Dockerfile` は `config` になります。
用途分類は `type` に入れません。
ローカルツール用の Go とメイン app 用の Go はどちらも `code` として保存し、
取得時に `repo` と `path` を見て解釈します。

## バックエンドの責務

FalkorDB はグラフメモリと関係性を持つ文脈を保存します。

Qdrant は意味ベクトルを保存し、類似検索を担います。

どちらも元リポジトリから再構築できるため、運用復旧は mem0 のエクスポートではなく
Git から始めます。

Compose 実行環境では、このリポジトリ内のローカル API パッケージが
Qdrant と FalkorDB の設定を mem0 OSS ライブラリへ渡します。
