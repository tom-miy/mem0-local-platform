# Model Provider Settings

mem0 uses two model paths:

- The embedder turns Markdown chunks and queries into vectors.
- The LLM extracts or rewrites memories when mem0 inference is enabled.

For repository indexing, embedding quality matters more than LLM size. The
GitHub sync path sends prepared Markdown chunks with `infer=false`, so a small
LLM is enough for the default workflow.

## Linux Ollama Install

Official Linux install:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify the service:

```bash
ollama --version
systemctl status ollama
```

Enable and start Ollama as a daemon:

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama
```

View daemon logs:

```bash
journalctl -e -u ollama
```

Pull the default models used by this repository:

```bash
ollama pull nomic-embed-text:latest
ollama pull qwen3:4b
```

Confirm the models are available:

```bash
ollama list
```

The default compose runtime includes an `ollama` service, so
`OLLAMA_BASE_URL=http://ollama:11434` works inside compose. If Ollama runs on the
host instead, set `OLLAMA_BASE_URL=http://host.docker.internal:11434`.

If you use the manual Ollama install instead of the install script, create the
systemd service described in the official Linux documentation before running
`systemctl enable ollama`.

## Local Ollama

Use this when the platform should stay fully local.

```env
MEM0_LLM_PROVIDER=ollama
MEM0_LLM_MODEL=qwen3:4b
MEM0_EMBEDDER_PROVIDER=ollama
MEM0_EMBEDDER_MODEL=nomic-embed-text:latest
MEM0_EMBEDDING_DIMS=768
OLLAMA_BASE_URL=http://ollama:11434
```

Pull the default models after starting compose:

```bash
mise run ollama-pull
```

`nomic-embed-text` uses 768 dimensions. Keep `MEM0_EMBEDDING_DIMS=768` unless
you change the embedding model and recreate the Qdrant collection.

## Host Ollama

Use this when Ollama runs on the host machine instead of inside compose.

```env
MEM0_LLM_PROVIDER=ollama
MEM0_LLM_MODEL=qwen3:4b
MEM0_EMBEDDER_PROVIDER=ollama
MEM0_EMBEDDER_MODEL=nomic-embed-text:latest
MEM0_EMBEDDING_DIMS=768
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

This is convenient for development, but compose is no longer fully
self-contained.

## Ollama Cloud

Use `MEM0_CONFIG_JSON` when the provider needs an explicit hosted endpoint or
API key.

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

If the hosted endpoint requires a token, keep it in `.env` or your runtime
secret store. Do not put real tokens in docs.

## OpenRouter

mem0 documents OpenRouter through the OpenAI provider path. Use it for the LLM
only, and keep embeddings on a stable embedding provider.

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

## OpenAI-Compatible Routers

For routers such as OpenRouter-compatible gateways, LiteLLM gateways, or local
LLM routers, prefer `MEM0_CONFIG_JSON` so the base URL, API key, model, vector
store, and graph store stay reviewable in one place.

Example for a LiteLLM-compatible router:

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

Use the base URL required by your router. Validate router-specific `base_url`
support before relying on it in production. mem0 provider adapters do not all
accept the same option names.

## Recommendation

Start with local Ollama:

- `qwen3:4b` for LLM when Japanese or mixed-language notes matter
- `nomic-embed-text:latest` for embeddings
- `MEM0_EMBEDDING_DIMS=768`

Move the LLM to OpenRouter, Ollama Cloud, or another router only if local model
latency or host resources become a problem. Keep the embedder stable unless you
are ready to recreate the Qdrant collection.

## Model Size Guidance

Use the smallest model that fits the job:

| Use case | Recommended level | Notes |
| --- | --- | --- |
| GitHub repository sync | embedder + small LLM | Sync sends prepared repository context chunks with `infer=false`; embedding quality matters most. |
| English-only Raycast or short notes | 3B local LLM | `llama3.2:3b` is enough for light cleanup when Japanese quality is not important. |
| Japanese or mixed-language notes | 4B to 8B multilingual LLM | Prefer `qwen3:4b` first, then `qwen3:8b` if quality is not enough. |
| Noisy transcripts or long notes | 8B+ local LLM or hosted mini model | Better extraction quality is useful here. |
| Complex reasoning over memories | hosted reasoning model | Use only when memory extraction needs real reasoning. |

For Ollama, start with `qwen3:4b` when Japanese quality matters. It is still
small enough for local use, while Qwen 3 documents support for 100+ languages
and dialects. Use `llama3.2:3b` only as the lowest-resource option.

Do not choose a model only because it is newer. `llama3.3` is a 70B model and
`llama4` is much larger; both are heavy for a local memory extraction service.
Their Ollama model pages do not list Japanese as an explicitly supported
language, so they are not the default recommendation for Japanese-heavy notes.

If you want stronger local reasoning and have the memory budget, consider:

- `qwen3:8b` for better multilingual extraction.
- `gpt-oss:20b` for heavier reasoning and agentic work.

For embeddings, keep `nomic-embed-text:latest` unless you are ready to recreate
the Qdrant collection. If Japanese retrieval quality is not enough, evaluate
`qwen3-embedding`, but verify the actual output dimensions locally and update
`MEM0_EMBEDDING_DIMS` before creating a new Qdrant collection.

For OpenAI-compatible hosted providers, a mini class model is usually enough for
mem0 extraction. OpenAI's current model list shows `o4-mini` as a fast,
cost-efficient reasoning model that has been succeeded by `GPT-5 mini`; use a
reasoning model only when extraction needs multi-step reasoning. For normal
developer knowledge indexing, prefer a smaller non-reasoning or mini model and
keep the embedder stable.

## References

- Ollama Linux install: <https://docs.ollama.com/linux>
- Ollama Qwen 3 model page: <https://ollama.com/library/qwen3>
- Ollama Qwen 3 Embedding model page: <https://ollama.com/library/qwen3-embedding>
- Ollama Llama 3.3 model page: <https://ollama.com/library/llama3.3>
- Ollama Llama 4 model page: <https://ollama.com/library/llama4>
- OpenAI `o4-mini` model page: <https://developers.openai.com/api/docs/models/o4-mini>
