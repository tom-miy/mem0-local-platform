"""Compatibility entrypoint for the requested repository layout.

Run `uv run mem0-local-mcp` in normal use. Direct script execution also works:
`python mcp/server.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mem0_local_platform_mcp.server import main  # noqa: E402


if __name__ == "__main__":
    main()

