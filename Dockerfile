FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY mcp ./mcp
COPY mem0_local_platform_api ./mem0_local_platform_api
COPY mem0_local_platform_mcp ./mem0_local_platform_mcp
COPY scripts ./scripts

RUN pip install --no-cache-dir uv \
  && uv sync --no-dev

CMD ["uv", "run", "mem0-local-api"]
