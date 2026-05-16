# tenant 運用ルール

tenant は mem0-local-platform におけるセキュリティ境界です。

tenant は repository grouping ではありません。
repo 名は metadata として保存します。

## 基本ルール

- tenant は読み取り境界と書き込み境界を表します。
- repository ごとに tenant を作りません。
- tenant 名は人間が運用判断できる粒度にします。
- client data や契約境界が違う場合は tenant を分けます。
- 同じ会社や個人の作業領域で、秘密境界が同じなら tenant を分けません。

## 推奨 tenant

```text
vault
work
client-*
agency-*
```

例:

```text
vault
work
upwork-18384728-acme
agency-991-example
```

## 避ける tenant

repo ごとの tenant:

```text
backend-testing-patterns
frontend-app
infra-scripts
```

これは避けます。

理由:

- tenant が増えすぎる
- read/write policy が複雑になる
- cross-repo context が使いにくくなる
- repo rename と security boundary が混ざる

## metadata schema

repository は metadata に入れます。

```json
{
  "tenant": "work",
  "repo": "backend-testing-patterns",
  "path": "docs/e2e.md",
  "type": "doc",
  "tags": ["testing", "e2e"]
}
```

`tenant` は isolation boundary です。
`repo` と `path` は retrieval metadata です。

## read/write policy

MCP runtime は readable tenants と write tenant を分けます。

```text
MEM0_READ_TENANTS=vault,work
MEM0_WRITE_TENANT=work
```

readable tenants は検索できる範囲です。
write tenant は `remember` が書き込む先です。

複数 tenant を読めても、書き込み先は 1 つに固定します。
これにより、agent が誤って別 tenant に記録する事故を避けます。

## tenant を増やす基準

tenant を増やしてよい場合:

- client / customer が違う
- 契約上の隔離が必要
- 個人 vault と work を分けたい
- agent に読ませてよい範囲が明確に違う

tenant を増やさない場合:

- repository が違うだけ
- docs の種類が違うだけ
- language / framework が違うだけ
- team 内の同じ作業領域で使うだけ

## 運用例

個人作業:

```text
MEM0_READ_TENANTS=vault,work
MEM0_WRITE_TENANT=work
```

client work:

```text
MEM0_READ_TENANTS=work,client-18384728-acme
MEM0_WRITE_TENANT=client-18384728-acme
```

client tenant で作業するときは、write tenant も client tenant に合わせます。
work tenant へ client 情報を書かないためです。

## レビュー観点

tenant 設定を変えるときは次を確認します。

- その tenant は本当に security boundary か
- repo 名や project 名を tenant にしていないか
- write tenant が現在の作業対象と一致しているか
- readable tenants に不要な client tenant が入っていないか
- GitHub Actions の `tenant` input が正しいか

