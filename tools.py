"""Yaku Canvas agent tools. The agent can drive the same board the desktop
canvas renders: add sources (auto-fetch transcript/text), list them, and run
grounded chats that answer only from connected sources."""

from __future__ import annotations

import json
from typing import Any, Callable

from . import service

_ADD_SCHEMA = {
    "type": "object",
    "properties": {
        "board_id": {"type": "string", "description": "Board to add to (created if missing; default 'main')"},
        "url": {"type": "string", "description": "A YouTube/TikTok/Reddit/web link, or a plain note"},
        "title": {"type": "string", "description": "Optional card title override"},
    },
    "required": ["url"],
}

_CHAT_SCHEMA = {
    "type": "object",
    "properties": {
        "board_id": {"type": "string"},
        "question": {"type": "string", "description": "What to write/ask, grounded in connected sources"},
        "node_ids": {"type": "array", "items": {"type": "string"},
                      "description": "Only these nodes are read (empty = all sources on the board)"},
    },
    "required": ["question"],
}

_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "board_id": {"type": "string"},
    },
}


def _board(board_id: str | None) -> dict:
    bid = board_id or "main"
    b = service.load_board(bid)
    if b is None:
        b = {"id": bid, "name": bid, "nodes": [], "edges": []}
    return b


def _next_node_id(b: dict) -> str:
    n = len(b["nodes"]) + 1
    return f"n{b['id']}-{n:03d}"


def _add_source(args: dict, **_kw) -> str:
    url = str(args.get("url", "")).strip()
    if not url:
        return json.dumps({"error": "url is required"})
    b = _board(args.get("board_id"))
    node_id = _next_node_id(b)
    fetched = service.fetch_source(url)
    node = {"id": node_id, "url": url, "title": args.get("title") or fetched["title"],
            "kind": service.classify_url(url)["kind"], "text": fetched["text"],
            "origin": fetched["origin"], "status": "ok" if fetched["text"] else "empty"}
    b["nodes"].append(node)
    service.save_board(b)
    summary = node["text"][:400] + ("..." if len(node["text"]) > 400 else "")
    return json.dumps({"board": b["id"], "node": {k: node[k] for k in
                       ("id", "title", "kind", "origin", "status")}, "preview": summary})


def _list_sources(args: dict, **_kw) -> str:
    bid = args.get("board_id")
    if bid:
        boards = [service.load_board(bid) or {"id": bid, "name": bid, "nodes": [], "edges": []}]
    else:
        boards = [service.load_board(b["id"]) or b for b in service.list_boards()]
    out = [{"board": b["id"], "name": b.get("name"),
            "nodes": [{"id": n["id"], "title": n.get("title"), "kind": n.get("kind"),
                       "status": n.get("status"), "chars": len(n.get("text", ""))}
                      for n in b["nodes"]]} for b in boards]
    return json.dumps(out or {"note": "no boards yet"})


def _chat(args: dict, **_kw) -> str:
    q = str(args.get("question", "")).strip()
    if not q:
        return json.dumps({"error": "question is required"})
    b = _board(args.get("board_id"))
    want = set(args.get("node_ids") or [])
    texts: dict[str, str] = {}
    for n in b["nodes"]:
        if want and n["id"] not in want:
            continue
        if n.get("text"):
            texts[n["id"]] = n["text"]
    if not texts:
        return json.dumps({"error": "no sources with text connected — add sources first (yaku_add_source)"})
    r = service.grounded_chat(q, texts)
    return json.dumps({"board": b["id"], "answer": r["answer"], "sources": r["sources"],
                       "provider": r["provider"], "model": r["model"]})


TOOL_DEFS: list[tuple[str, dict, Callable, str]] = [
    ("yaku_add_source",
     {"description": "Add a source card to a Yaku canvas board: paste a YouTube/TikTok/Reddit/web link or a plain note; the transcript/page text is fetched automatically and cached.",
      "parameters": _ADD_SCHEMA},
     _add_source, "yaku"),
    ("yaku_list_sources",
     {"description": "List boards and their source cards (ids, titles, kinds, sizes).",
      "parameters": _LIST_SCHEMA},
     _list_sources, "yaku"),
    ("yaku_chat",
     {"description": "Grounded chat over the board: answers ONLY from the sources connected to the given board (or node_ids subset), citing them as [S1], [S2].",
      "parameters": _CHAT_SCHEMA},
     _chat, "yaku"),
]


def _demo() -> None:  # pragma: no cover
    b = _board(None); assert b["id"] == "main"
    assert set(n for n, _, _, _ in TOOL_DEFS) == {"yaku_add_source", "yaku_list_sources", "yaku_chat"}
    print("tools self-check OK")


if __name__ == "__main__":
    _demo()