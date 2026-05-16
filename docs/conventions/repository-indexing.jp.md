# リポジトリ索引作成の規約

リポジトリ名はメタデータです。テナントではありません。

セキュリティ境界にはテナントを使い、プロジェクト単位の検索には `repo`
メタデータを使います。

## 索引対象のリポジトリ文脈

デフォルトの取り込みルールでは次を索引します。

- `README.md`
- `README*.md`
- `docs/**/*.md`
- `adr/**/*.md`
- `adrs/**/*.md`
- `**/*.go`
- `**/*.py`
- `**/*.ts`
- `**/*.tsx`
- `**/*.js`
- `**/*.jsx`
- `**/*.rs`
- `**/*.java`
- `**/*.kt`
- `**/*.sql`
- `**/*.sh`
- `api.yaml`
- `openapi.yaml`
- `**/*.yaml`
- `**/*.yml`
- `**/*.json`
- `**/*.toml`
- `**/*.proto`
- `Dockerfile`
- `compose.yml`
- `Makefile`

CLI は、生成物や依存関係が多いパスを除外します。
例は `node_modules`、`dist`、`vendor`、`coverage`、`build` です。
`.env`、`secrets/**`、`data/**` のような秘密情報や実行時状態も除外します。
PDF、Office 文書、画像、アーカイブ、音声や動画も除外します。
これらはファイル種別ごとの抽出処理を用意してから索引対象にします。

リポジトリごとのパスルールは、Git 管理する設定ファイルに置けます。

```text
.mem0-sync.yml
```

共通ワークフローは、このファイルがあれば読み込みます。
なければ mem0-local-platform 側の `.mem0-sync.default.yml` を使います。
共通ワークフロー本体には include/exclude の実体を置きません。
YAML のキーは `include` と `exclude` です。

ローカルでは次で include/exclude へ変換できます。

```bash
mise run sync-path-rules
```

除外は取り込み対象の判定より先に適用されます。

## 同期モード

共通ワークフローは 2 つのファイル一覧モードを持ちます。

- `changed`: push 差分で変更されたファイルだけを索引します。
- `full`: Git 管理下の全ファイルから include/exclude ルールを通ったものを索引します。

初回投入、ルール変更後、バックエンド状態の再構築後は `full` を使います。

`changed` では、削除されたファイルやリネーム元の path も取り込み CLI に渡します。
ファイルを再索引する前に同じ `tenant + repo + path` の既存 chunk を削除するため、
消した見出しや削除済みファイルの古い chunk が mem0 側に残らないようにします。

## 分割

Markdown は見出し単位で分割します。
取得した断片を元の文書構造へ戻せるように、見出し階層をメタデータとして保存します。
コード、API 定義、設定ファイルもリポジトリ文脈として取り込み、ファイルパス、
種別、リポジトリ名をメタデータとして保存します。

`type` は取り込み時に Python 側で `path` から自動判定します。
現状の値は次です。

```text
readme
adr
doc
code
config
markdown
```

`type` はファイルの大分類です。
`ローカルツール用の Go` と `メイン app 用の Go` のような用途分類は、
どちらも `type=code` として保存し、取得時に `repo` や `path` を見て解釈します。
たとえば `tools/**`、`scripts/**`、`cmd/**` の意味はリポジトリごとに変わるため、
mem0 に固定メタデータとして保存しません。
