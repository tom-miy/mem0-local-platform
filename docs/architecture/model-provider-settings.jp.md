# モデルプロバイダ設定

mem0 ではモデルの役割が 2 つあります。

- 埋め込みモデルは、Markdown の断片と検索文をベクトルにします。
- LLM は、mem0 の推論を有効にしたときに記憶を抽出または整理します。

リポジトリ同期では、LLM の大きさより埋め込みモデルの品質が重要です。
GitHub 同期では整理済みの Markdown 断片を `infer=false` で送るため、
標準運用では小さな LLM で足ります。

## Linux への Ollama インストール

公式の Linux インストール手順です。

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

サービスを確認します。

```bash
ollama --version
systemctl status ollama
```

Ollama をデーモンとして起動し、自動起動を有効にします。

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama
```

ログを確認します。

```bash
journalctl -e -u ollama
```

このリポジトリの標準モデルを取得します。

```bash
ollama pull bge-m3
ollama pull qwen3.5:4b
```

取得済みモデルを確認します。

```bash
ollama list
```

デフォルトの compose 実行環境には `ollama` サービスが含まれるため、
compose 内では `OLLAMA_BASE_URL=http://ollama:11434` を使えます。
Ollama をホスト側で動かす場合は
`OLLAMA_BASE_URL=http://host.docker.internal:11434` を使います。

インストールスクリプトではなく手動インストールを使う場合は、
公式 Linux ドキュメントにある systemd サービスを作ってから
`systemctl enable ollama` を実行します。

## ローカル Ollama

実行基盤をできるだけローカルで閉じたい場合の設定です。

```env
MEM0_LLM_PROVIDER=ollama
MEM0_LLM_MODEL=qwen3.5:4b
MEM0_LLM_TEMPERATURE=0.1
MEM0_EMBEDDER_PROVIDER=ollama
MEM0_EMBEDDER_MODEL=bge-m3
MEM0_EMBEDDING_DIMS=1024
OLLAMA_BASE_URL=http://ollama:11434
```

compose 起動後にデフォルトモデルを取得します。

```bash
mise run ollama-pull
```

`bge-m3` は 1024 次元の dense embedding を返します。
埋め込みモデルを変えて Qdrant のコレクションを作り直す場合以外は、
`MEM0_EMBEDDING_DIMS=1024` のままにします。

## ホスト側 Ollama

Ollama を Docker Compose の外、つまりホスト側で動かす場合の設定です。

```env
MEM0_LLM_PROVIDER=ollama
MEM0_LLM_MODEL=qwen3.5:4b
MEM0_LLM_TEMPERATURE=0.1
MEM0_EMBEDDER_PROVIDER=ollama
MEM0_EMBEDDER_MODEL=bge-m3
MEM0_EMBEDDING_DIMS=1024
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

開発中は便利ですが、Compose だけでは完結しなくなります。

## Ollama Cloud

ホストされた Ollama 互換エンドポイントや API キーが必要な場合は、
`MEM0_CONFIG_JSON` で明示します。

```env
MEM0_CONFIG_JSON='{
  "vector_store": {
    "provider": "qdrant",
    "config": {
      "host": "qdrant",
      "port": 6333,
      "collection_name": "developer_memories",
      "embedding_model_dims": 1024
    }
  },
  "graph_store": {
    "provider": "falkordb",
    "config": {
      "url": "redis://falkordb:6379"
    }
  },
  "llm": {
    "provider": "ollama",
    "config": {
      "model": "qwen3.5:4b",
      "temperature": 0.1,
      "ollama_base_url": "https://ollama.example.com"
    }
  },
  "embedder": {
    "provider": "ollama",
    "config": {
      "model": "bge-m3",
      "ollama_base_url": "https://ollama.example.com"
    }
  }
}'
```

トークンが必要な場合は `.env` か実行環境のシークレット管理に置きます。
実トークンをドキュメントに書いてはいけません。

## OpenRouter

mem0 の資料では、OpenRouter は OpenAI プロバイダ経由で扱います。
LLM だけ OpenRouter に寄せ、埋め込みは安定した埋め込みプロバイダに残すのが
分かりやすいです。

```env
OPENROUTER_API_KEY=...
MEM0_CONFIG_JSON='{
  "vector_store": {
    "provider": "qdrant",
    "config": {
      "host": "qdrant",
      "port": 6333,
      "collection_name": "developer_memories",
      "embedding_model_dims": 1024
    }
  },
  "graph_store": {
    "provider": "falkordb",
    "config": {
      "url": "redis://falkordb:6379"
    }
  },
  "llm": {
    "provider": "openai",
    "config": {
      "model": "meta-llama/llama-3.1-8b-instruct"
    }
  },
  "embedder": {
    "provider": "ollama",
    "config": {
      "model": "bge-m3",
      "ollama_base_url": "http://ollama:11434"
    }
  }
}'
```

## OpenAI 互換ルーター

Crazy Router、LiteLLM Gateway、ローカル LLM ルーターなどを使う場合は、
`MEM0_CONFIG_JSON` にまとめるのが安全です。
接続先、API キー、モデル名、Qdrant、FalkorDB の設定が 1 か所で確認できます。

LiteLLM 互換ルーターの例:

```env
OPENAI_API_KEY=...
MEM0_CONFIG_JSON='{
  "vector_store": {
    "provider": "qdrant",
    "config": {
      "host": "qdrant",
      "port": 6333,
      "collection_name": "developer_memories",
      "embedding_model_dims": 1024
    }
  },
  "graph_store": {
    "provider": "falkordb",
    "config": {
      "url": "redis://falkordb:6379"
    }
  },
  "llm": {
    "provider": "litellm",
    "config": {
      "model": "openai/gpt-4.1-mini",
      "base_url": "https://router.example.com/v1"
    }
  },
  "embedder": {
    "provider": "ollama",
    "config": {
      "model": "bge-m3",
      "ollama_base_url": "http://ollama:11434"
    }
  }
}'
```

`base_url` には使うルーターの接続先を指定します。
本番で使う前に、使うルーターで `base_url` などのオプション名が
mem0 のプロバイダ実装に渡るか確認してください。
mem0 のプロバイダごとに受け付ける設定名が同じとは限りません。

## 推奨

最初はローカル Ollama で始めます。

- 日本語や日英混在メモを扱う場合、LLM は `qwen3.5:4b`
- 埋め込みは `bge-m3`
- 次元数は `MEM0_EMBEDDING_DIMS=1024`

ローカルモデルの遅さやマシン負荷が問題になったら、LLM だけ OpenRouter、
Ollama Cloud、または別のルーターに移します。
埋め込みモデルは、Qdrant のコレクションを作り直す準備ができるまで変えません。

役割は明確に分けます。

- `qwen3.5:4b`: 推論、抽出、メタデータ生成、要約、MCP/tool 層
- `bge-m3`: 取得と意味検索の層

`qwen3.5:4b` を埋め込みモデルとして使ってはいけません。
この基盤では、生成品質よりも検索品質の方が重要です。

## モデルサイズの目安

必要な仕事に対して、できるだけ小さいモデルを使います。

| 用途 | 目安 | 補足 |
| --- | --- | --- |
| GitHub リポジトリ同期 | 埋め込みモデル + 小さな LLM | 同期は `infer=false` の整理済みリポジトリ文脈を送るため、埋め込み品質が重要です。 |
| 英語だけの Raycast や短いメモ | ローカル 3B | 日本語品質を重視しないなら `llama3.2:3b` でも足ります。 |
| 日本語や日英混在のメモ | 多言語向け 4B から 8B | まず `qwen3.5:4b` を使います。抽出品質が足りない場合だけ、より大きい多言語ローカルモデルを検証します。 |
| ノイズの多い文字起こしや長いメモ | ローカル 8B 以上、またはホスト型 mini モデル | 抽出品質を上げたい場合に使います。 |
| 記憶をまたぐ複雑な推論 | ホスト型の推論モデル | 本当に推論が必要な場合だけ使います。 |

日本語品質を重視するなら、Ollama ではまず `qwen3.5:4b` から始めます。
常時起動しやすい軽さで、開発用メモリの抽出、メタデータ生成、要約、
MCP/tool 連携には十分な強さがあります。
`llama3.2:3b` は、メモリを強く節約したい場合の最低ラインとして扱います。

新しいモデルだからという理由だけで選ばないでください。
`llama3.3` は 70B、`llama4` はさらに大きいモデルで、ローカルの記憶抽出用には
重すぎます。また、Ollama のモデルページで日本語が明示された対応言語として
挙がっていないため、日本語メモ中心の標準候補にはしません。

ローカルでより強い抽出や推論が必要で、メモリに余裕がある場合は、
埋め込みモデルを変える前に、抽出用のより大きい多言語ローカルモデルを検証します。

埋め込みモデルは、まず `bge-m3` のままにします。
GitHub リポジトリ、Obsidian Markdown、日英混在メモ、コードや API 定義の検索では、
LLM の生成品質よりも埋め込み品質が検索結果を左右します。

OpenAI 互換のホスト型プロバイダでは、mem0 の記憶抽出には mini クラスで
足りることが多いです。OpenAI の現行モデル一覧では、`o4-mini` は高速で
費用効率のよい推論モデルですが、後継として `GPT-5 mini` が示されています。
通常の開発知識の索引作成では推論モデルを最初から使わず、
小さめの非推論モデルまたは mini クラスを使い、埋め込みモデルを安定させます。

## 参照

- Ollama Linux インストール: <https://docs.ollama.com/linux>
- Ollama BGE-M3 モデルページ: <https://ollama.com/library/bge-m3>
- Ollama Llama 3.3 モデルページ: <https://ollama.com/library/llama3.3>
- Ollama Llama 4 モデルページ: <https://ollama.com/library/llama4>
- OpenAI `o4-mini` モデルページ: <https://developers.openai.com/api/docs/models/o4-mini>
