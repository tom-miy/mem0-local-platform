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
ollama pull nomic-embed-text:latest
ollama pull qwen3:4b
```

取得済みモデルを確認します。

```bash
ollama list
```

Ollama をホスト側で動かし、mem0 を Docker Compose で動かす場合は
`OLLAMA_BASE_URL=http://host.docker.internal:11434` を使います。
Ollama も Compose サービスとして動かす場合は
`OLLAMA_BASE_URL=http://ollama:11434` を使います。

インストールスクリプトではなく手動インストールを使う場合は、
公式 Linux ドキュメントにある systemd サービスを作ってから
`systemctl enable ollama` を実行します。

## ローカル Ollama

実行基盤をできるだけローカルで閉じたい場合の設定です。

```env
MEM0_LLM_PROVIDER=ollama
MEM0_LLM_MODEL=qwen3:4b
MEM0_EMBEDDER_PROVIDER=ollama
MEM0_EMBEDDER_MODEL=nomic-embed-text:latest
MEM0_EMBEDDING_DIMS=768
OLLAMA_BASE_URL=http://ollama:11434
```

`nomic-embed-text` は 768 次元です。
埋め込みモデルを変えて Qdrant のコレクションを作り直す場合以外は、
`MEM0_EMBEDDING_DIMS=768` のままにします。

## ホスト側 Ollama

Ollama を Docker Compose の外、つまりホスト側で動かす場合の設定です。

```env
MEM0_LLM_PROVIDER=ollama
MEM0_LLM_MODEL=qwen3:4b
MEM0_EMBEDDER_PROVIDER=ollama
MEM0_EMBEDDER_MODEL=nomic-embed-text:latest
MEM0_EMBEDDING_DIMS=768
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
      "embedding_model_dims": 768
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
      "model": "qwen3:4b",
      "ollama_base_url": "https://ollama.example.com"
    }
  },
  "embedder": {
    "provider": "ollama",
    "config": {
      "model": "nomic-embed-text:latest",
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
      "embedding_model_dims": 768
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
      "model": "nomic-embed-text:latest",
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
      "embedding_model_dims": 768
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
      "model": "nomic-embed-text:latest",
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

- 日本語や日英混在メモを扱う場合、LLM は `qwen3:4b`
- 埋め込みは `nomic-embed-text:latest`
- 次元数は `MEM0_EMBEDDING_DIMS=768`

ローカルモデルの遅さやマシン負荷が問題になったら、LLM だけ OpenRouter、
Ollama Cloud、または別のルーターに移します。
埋め込みモデルは、Qdrant のコレクションを作り直す準備ができるまで変えません。

## モデルサイズの目安

必要な仕事に対して、できるだけ小さいモデルを使います。

| 用途 | 目安 | 補足 |
| --- | --- | --- |
| GitHub Markdown 同期 | 埋め込みモデル + 小さな LLM | 同期は `infer=false` の整理済み断片を送るため、埋め込み品質が重要です。 |
| 英語だけの Raycast や短いメモ | ローカル 3B | 日本語品質を重視しないなら `llama3.2:3b` でも足ります。 |
| 日本語や日英混在のメモ | 多言語向け 4B から 8B | まず `qwen3:4b`、足りなければ `qwen3:8b` を使います。 |
| ノイズの多い文字起こしや長いメモ | ローカル 8B 以上、またはホスト型 mini モデル | 抽出品質を上げたい場合に使います。 |
| 記憶をまたぐ複雑な推論 | ホスト型の推論モデル | 本当に推論が必要な場合だけ使います。 |

日本語品質を重視するなら、Ollama ではまず `qwen3:4b` から始めます。
Qwen 3 は 100 以上の言語と方言への対応を説明しており、日本語や日英混在の
メモには Llama 3.2 3B より選びやすいです。
`llama3.2:3b` は、メモリを強く節約したい場合の最低ラインとして扱います。

新しいモデルだからという理由だけで選ばないでください。
`llama3.3` は 70B、`llama4` はさらに大きいモデルで、ローカルの記憶抽出用には
重すぎます。また、Ollama のモデルページで日本語が明示された対応言語として
挙がっていないため、日本語メモ中心の標準候補にはしません。

ローカルでより強い抽出や推論が必要で、メモリに余裕がある場合:

- `qwen3:8b`: 日本語や多言語の抽出品質を上げたい場合。
- `gpt-oss:20b`: 推論やエージェント寄りの処理を重くしてよい場合。

埋め込みモデルは、まず `nomic-embed-text:latest` のままにします。
日本語検索の品質が足りない場合は `qwen3-embedding` を検証します。
ただし、実際の出力次元をローカルで確認し、`MEM0_EMBEDDING_DIMS` を合わせてから
Qdrant のコレクションを作り直してください。

OpenAI 互換のホスト型プロバイダでは、mem0 の記憶抽出には mini クラスで
足りることが多いです。OpenAI の現行モデル一覧では、`o4-mini` は高速で
費用効率のよい推論モデルですが、後継として `GPT-5 mini` が示されています。
通常の開発知識の索引作成では推論モデルを最初から使わず、
小さめの非推論モデルまたは mini クラスを使い、埋め込みモデルを安定させます。

## 参照

- Ollama Linux インストール: <https://docs.ollama.com/linux>
- Ollama Qwen 3 モデルページ: <https://ollama.com/library/qwen3>
- Ollama Qwen 3 Embedding モデルページ: <https://ollama.com/library/qwen3-embedding>
- Ollama Llama 3.3 モデルページ: <https://ollama.com/library/llama3.3>
- Ollama Llama 4 モデルページ: <https://ollama.com/library/llama4>
- OpenAI `o4-mini` モデルページ: <https://developers.openai.com/api/docs/models/o4-mini>
