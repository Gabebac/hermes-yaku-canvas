"""Yaku Canvas backend: REST for the desktop canvas.

Boards live in plugin-data/yaku-canvas/boards/*.json (same files the agent
tools write), so the canvas and the agent share one store. Fetching a source
uses the REA-recovered Yaku chain (youtube -> piped -> kome, tikwm, reddit
json, plain page fetch). Chat runs through the host-owned PluginLlm.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

# Standalone dashboard import vs in-package import
try:
    from .. import service  # type: ignore
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import service  # type: ignore

router = APIRouter()


class NodeIn(BaseModel):
    id: str | None = None
    url: str
    x: float = 0
    y: float = 0


class NodePatch(BaseModel):
    title: str | None = None
    text: str | None = None
    x: float | None = None
    y: float | None = None


class EdgeIn(BaseModel):
    source: str
    target: str


class BoardIn(BaseModel):
    id: str
    name: str = "Untitled board"


class ChatIn(BaseModel):
    board_id: str
    question: str
    node_ids: list[str] = []


@router.get("/boards")
def get_boards() -> dict:
    return {"boards": service.list_boards()}


@router.get("/boards/{board_id}")
def get_board(board_id: str) -> Any:
    return service.load_board(board_id) or {"id": board_id, "name": board_id, "nodes": [], "edges": []}


@router.put("/boards/{board_id}")
def put_board(board_id: str, board: BoardIn) -> dict:
    b = service.load_board(board_id) or {"id": board_id, "name": board_id, "nodes": [], "edges": []}
    b["name"] = board.name
    service.save_board(b)
    return {"ok": True}


@router.post("/boards/{board_id}/nodes")
def add_node(board_id: str, node: NodeIn) -> dict:
    b = service.load_board(board_id) or {"id": board_id, "name": board_id, "nodes": [], "edges": []}
    fetched = service.fetch_source(node.url)
    n = {
        "id": node.id or f"n{board_id}-{len(b['nodes']) + 1:03d}",
        "url": node.url, "title": fetched["title"],
        "kind": service.classify_url(node.url)["kind"],
        "text": fetched["text"], "origin": fetched["origin"],
        "status": "ok" if fetched["text"] else "empty",
        "x": node.x, "y": node.y,
    }
    b["nodes"].append(n)
    service.save_board(b)
    # node document minus the full text for the wire; UI pulls text via /text
    return {"node": {k: v for k, v in n.items() if k != "text"}, "chars": len(n["text"])}


@router.patch("/boards/{board_id}/nodes/{node_id}")
def move_node(board_id: str, node_id: str, x: float = None, y: float = None) -> dict:
    b = service.load_board(board_id)
    if not b:
        return {"error": "board not found"}
    for n in b["nodes"]:
        if n["id"] == node_id:
            if x is not None: n["x"] = x
            if y is not None: n["y"] = y
    service.save_board(b)
    return {"ok": True}


@router.put("/boards/{board_id}/nodes/{node_id}")
def edit_node(board_id: str, node_id: str, patch: NodePatch) -> dict:
    """User edits from the canvas: rename, rewrite the source text, or make a
    plain note card (kind=note, no fetch). Agent tools see the same fields."""
    b = service.load_board(board_id)
    if not b:
        return {"error": "board not found"}
    for n in b["nodes"]:
        if n["id"] == node_id:
            if patch.title is not None: n["title"] = patch.title
            if patch.text is not None:
                n["text"] = patch.text
                n["status"] = "ok" if patch.text.strip() else "empty"
            if patch.x is not None: n["x"] = patch.x
            if patch.y is not None: n["y"] = patch.y
            service.save_board(b)
            return {"ok": True}
    return {"error": "node not found"}


@router.post("/boards/{board_id}/notes")
def add_note(board_id: str, note: NodePatch, x: float = 0, y: float = 0) -> dict:
    """Plain text note card — no URL, no fetch. Becomes chat context like any source."""
    b = service.load_board(board_id) or {"id": board_id, "name": board_id, "nodes": [], "edges": []}
    n = {
        "id": f"n{board_id}-{len(b['nodes']) + 1:03d}",
        "url": "", "title": note.title or "Note",
        "kind": "note", "text": note.text or "", "origin": "note",
        "status": "ok" if (note.text or "").strip() else "empty",
        "x": x, "y": y,
    }
    b["nodes"].append(n)
    service.save_board(b)
    return {"node": n}


@router.delete("/boards/{board_id}/nodes/{node_id}")
def delete_node(board_id: str, node_id: str) -> dict:
    b = service.load_board(board_id)
    if not b:
        return {"error": "board not found"}
    b["nodes"] = [n for n in b["nodes"] if n["id"] != node_id]
    b["edges"] = [e for e in b["edges"] if e["source"] != node_id and e["target"] != node_id]
    service.save_board(b)
    return {"ok": True}


@router.post("/boards/{board_id}/edges")
def add_edge(board_id: str, edge: EdgeIn) -> dict:
    b = service.load_board(board_id) or {"id": board_id, "nodes": [], "edges": [], "name": board_id}
    if edge not in b["edges"]:
        b["edges"].append({"source": edge.source, "target": edge.target})
        service.save_board(b)
    return {"ok": True, "edges": b["edges"]}


@router.delete("/boards/{board_id}/edges")
def delete_edge(board_id: str, source: str = "", target: str = "") -> dict:
    """Click a wire on the canvas to cut it."""
    b = service.load_board(board_id)
    if not b:
        return {"error": "board not found"}
    before = len(b["edges"])
    b["edges"] = [e for e in b["edges"] if not (e["source"] == source and e["target"] == target)]
    service.save_board(b)
    return {"ok": True, "removed": before - len(b["edges"])}


@router.get("/boards/{board_id}/nodes/{node_id}/text")
def node_text(board_id: str, node_id: str) -> dict:
    b = service.load_board(board_id) or {}
    for n in b.get("nodes", []):
        if n["id"] == node_id:
            return {"id": node_id, "text": n.get("text", ""), "origin": n.get("origin")}
    return {"error": "node not found"}


@router.post("/chat")
def chat(body: ChatIn) -> dict:
    b = service.load_board(body.board_id)
    if not b:
        return {"error": "board not found"}
    want = set(body.node_ids)
    texts = {}
    for n in b["nodes"]:
        if want and n["id"] not in want:
            continue
        if n.get("text"):
            texts[n["id"]] = n["text"]
    if not texts:
        return {"error": "no sources connected"}
    r = service.grounded_chat(body.question, texts)
    return {"answer": r["answer"], "sources": r["sources"], "provider": r["provider"], "model": r["model"]}


def _demo() -> None:  # pragma: no cover
    import inspect
    routes = [r.path for r in router.routes]
    assert "/chat" in routes and "/boards/{board_id}/edges" in routes, routes
    print("plugin_api self-check OK:", len(routes), "routes")


if __name__ == "__main__":
    _demo()