"""Yaku Canvas — Hermes plugin package.

Bring the Yaku workflow (getyaku.com desktop app, REA-reconstructed) into
Hermes: an infinite canvas of research sources (YouTube/TikTok/Reddit links,
notes, web pages) wired into AI chats that answer ONLY from connected sources.

Components:
- tools.py            agent-facing tools (add source, list, grounded chat)
- service.py          transcript/extract service + storage (plugin-data dir)
- desktop/plugin.js   the canvas UI for the Hermes desktop app
- dashboard/          (none: tools + desktop cover the feature; kept lean)

Storage layout (plugin_data_dir("yaku-canvas")):
    boards/<board>.json   board documents (nodes + edges)
    transcripts/<hash>.txt cached extracted source text
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("yaku_canvas")


def register(ctx) -> None:
    """Register the three agent tools. UI is loaded by the desktop app
    directly from desktop/plugin.js (unified-package door)."""
    from . import tools as yaku_tools

    for name, schema, handler, toolset in yaku_tools.TOOL_DEFS:
        ctx.register_tool(
            name=name,
            toolset=toolset,
            schema={"name": name, "description": schema["description"], "parameters": schema["parameters"]},
            handler=handler,
            description=schema["description"],
            emoji="\U0001F5BC",
        )
    logger.info("yaku-canvas tools registered")


# expose for hermes plugins doctor capability probe
__all__ = ["register"]


def _demo() -> None:  # pragma: no cover - manual smoke check
    from .service import classify_url
    assert classify_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")["kind"] == "youtube"
    assert classify_url("https://www.reddit.com/r/Python/")["kind"] == "reddit"
    assert classify_url("just a thought")["kind"] == "note"
    assert classify_url("https://example.com/blog/post")["kind"] == "web"
    print("yaku-canvas self-check OK")


if __name__ == "__main__":
    _demo()
