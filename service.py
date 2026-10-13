"""Yaku Canvas service layer: source classification, transcript/extract fetch,
board persistence, and grounded chat. Mirrors the fetch chain REA recovered
from Yaku's own api/*.js (youtube -> piped -> kome; tikwm for TikTok; shreddit
DOM json for Reddit; cheerio-style text extraction for plain web pages)."""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from plugins.plugin_storage import plugin_data_dir

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
PIPED_INSTANCES = [
    "https://api.piped.private.coffee",
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
]

_BOARDS_DIR = "boards"
_TX_DIR = "transcripts"


# ---------------------------------------------------------------- storage

def _boards_dir() -> Path:
    p = plugin_data_dir("yaku-canvas") / _BOARDS_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def _tx_dir() -> Path:
    p = plugin_data_dir("yaku-canvas") / _TX_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_board(board: dict) -> Path:
    path = _boards_dir() / f"{board['id']}.json"
    path.write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")
    return path


def load_board(board_id: str) -> dict | None:
    path = _boards_dir() / f"{board_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_boards() -> list[dict]:
    out = []
    for p in sorted(_boards_dir().glob("*.json")):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
            out.append({"id": b["id"], "name": b.get("name", b["id"]),
                        "nodes": len(b.get("nodes", [])),
                        "edges": len(b.get("edges", []))})
        except Exception:
            continue
    return out


def _cache_get(key: str) -> str | None:
    p = _tx_dir() / f"{hashlib.sha1(key.encode()).hexdigest()}.txt"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None


def _cache_put(key: str, text: str) -> None:
    p = _tx_dir() / f"{hashlib.sha1(key.encode()).hexdigest()}.txt"
    p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- fetch helpers

def _http(url: str, data: bytes | None = None, headers: dict | None = None,
          timeout: int = 25) -> bytes:
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _http_json(url: str, **kw) -> dict:
    return json.loads(_http(url, **kw))


# ---------------------------------------------------------------- classify

def classify_url(url: str) -> dict:
    """One classifier shared by tools and the desktop UI (same rules Yaku uses)."""
    s = url.strip()
    low = s.lower()
    if re.search(r"youtube\.com/(watch|shorts|playlist)|youtu\.be/", low):
        return {"kind": "youtube", "source_id": _yt_id(s)}
    if "tiktok.com" in low:
        return {"kind": "tiktok"}
    if "reddit.com" in low:
        return {"kind": "reddit"}
    if re.search(r"instagram|linkedin|facebook|threads\.net|twitter\.com|(^|\.)x\.com", low):
        return {"kind": "social"}
    if s.startswith("http://") or s.startswith("https://"):
        return {"kind": "web"}
    return {"kind": "note"}


def _yt_id(url: str) -> str | None:
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|/embed/)([\w-]{11})", url)
    return m.group(1) if m else None


# ---------------------------------------------------------------- transcript chain

def _yt_via_piped(vid: str) -> str | None:
    for inst in PIPED_INSTANCES:
        try:
            d = _http_json(f"{inst}/streams/{vid}", timeout=15)
            subs = d.get("subtitles") or []
            if not subs:
                continue
            url = subs[0].get("url")
            if not url:
                continue
            raw = _http(url, timeout=20).decode("utf-8", "replace")
            return _vtt_to_text(raw)
        except Exception:
            continue
    return None


def _vtt_to_text(raw: str) -> str:
    lines = []
    for line in raw.splitlines():
        if not line.strip() or line.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")) \
                or "-->" in line or re.fullmatch(r"\d+", line.strip()):
            continue
        t = re.sub(r"<[^>]+>", "", line).strip()
        if t and (not lines or t != lines[-1]):
            lines.append(t)
    return " ".join(lines)


def _yt_via_api(vid: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        t = YouTubeTranscriptApi().fetch(vid)
        return " ".join(s.text for s in t)
    except Exception:
        return None


def _yt_via_kome(url: str) -> str | None:
    try:
        body = json.dumps({"video_id": url}).encode()
        d = _http_json("https://kome.ai/api/transcript", data=body, headers={
            "Content-Type": "application/json", "Origin": "https://kome.ai",
            "Referer": "https://kome.ai/tools/youtube-transcript-generator"}, timeout=20)
        return (d.get("transcript") or d.get("text") or "").strip() or None
    except Exception:
        return None


def _tiktok_via_tikwm(url: str) -> str | None:
    # Yaku's get-tiktok-audio.js -> tikwm /api/ (transcripts are scarce on TikTok;
    # Yaku transcribes the audio with a Whisper provider — we surface the desc text)
    try:
        d = _http_json("https://www.tikwm.com/api/?url=" + urllib.parse.quote(url, safe=""), timeout=20)
        data = d.get("data") or {}
        parts = [data.get("title") or "", data.get("origin_cover") and "" or ""]
        text = " ".join(p for p in parts if p).strip()
        return text or None
    except Exception:
        return None


def _reddit_text(url: str) -> str | None:
    for u in (url.rstrip("/") + ".json", url.replace("www.reddit", "old.reddit").rstrip("/") + ".json"):
        try:
            data = _http_json(u, headers={"Accept": "application/json"}, timeout=20)
            if isinstance(data, list) and data:
                post = data[0]["data"]["children"][0]["data"]
                lines = [f"Reddit post: {post.get('title', '')}",
                         f"Subreddit: {post.get('subreddit', '')}  Author: u/{post.get('author', '')}"]
                if post.get("selftext"):
                    lines.append(post["selftext"])
                comments = []
                try:
                    for c in data[1]["data"]["children"][:25]:
                        d = c.get("data", {})
                        if d.get("body"):
                            comments.append(f"u/{d.get('author', '?')} (+{d.get('score', 0)}): {d['body']}")
                except Exception:
                    pass
                if comments:
                    lines.append("Top comments:\n" + "\n\n".join(comments))
                return "\n\n".join(lines)
        except Exception:
            continue
    return None


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "head"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP or (tag, ()) == ("meta", ()):
            if tag in self._SKIP:
                self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title = data.strip()
        elif not self._skip_depth and data.strip():
            self._chunks.append(data.strip())


def _web_text(url: str) -> tuple[str | None, str]:
    raw = _http(url, timeout=25).decode("utf-8", "replace")
    ex = _TextExtractor()
    ex.feed(raw)
    text = " ".join(ex._chunks)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return (text or None), (ex.title or url)


# ---------------------------------------------------------------- public API

def fetch_source(url: str) -> dict:
    """Fetch readable text for one source. Returns {text, title, origin}.
    Never raises: error paths return text='' and origin='error:<reason>'."""
    cls = classify_url(url)
    kind = cls["kind"]
    cached = _cache_get(url)
    if cached:
        title, _, text = cached.partition("\n")
        return {"text": text, "title": title or url, "origin": "cache"}

    text, title, origin = "", "", "none"
    try:
        if kind == "youtube":
            vid = cls.get("source_id")
            for fn, arg in ((_yt_via_api, vid), (_yt_via_piped, vid), (_yt_via_kome, url)):
                if not arg:
                    continue
                text = fn(arg)
                if text:
                    origin = fn.__name__
                    break
            title = "YouTube video"
        elif kind == "tiktok":
            text = _tiktok_via_tikwm(url)
            origin = "tikwm"
            title = "TikTok post"
        elif kind == "reddit":
            text = _reddit_text(url)
            origin = "reddit-json"
            title = "Reddit post"
        elif kind == "web":
            text, title = _web_text(url)
            origin = "fetch"
        else:  # note
            text, title, origin = url, "Note", "inline"
    except Exception as e:
        text, origin = "", f"error:{type(e).__name__}: {e}"

    title = html_mod.unescape(title or url)[:120]
    _cache_put(url, f"{title}\n{text}")
    return {"text": text, "title": title, "origin": origin}


import urllib.parse  # noqa: E402  (used by _tiktok_via_tikwm)


# ---------------------------------------------------------------- grounded chat

YAKU_SYSTEM = (
    "You are Yaku, a content-writing assistant on a research canvas. "
    "You answer ONLY from the connected sources the user provides. Ground every "
    "claim in a source and cite it inline as [S1], [S2] matching the numbered "
    "sources. If the connected sources do not contain the answer, say so plainly "
    "instead of inventing content. Write in the user's language."
)


def grounded_chat(question: str, source_texts: dict[str, str], history: list | None = None,
                  max_tokens: int = 900) -> dict:
    """One grounded completion via the host-owned LLM. Returns {answer, sources}."""
    from agent.plugin_llm import PluginLlm

    numbered, refs = [], []
    for i, (sid, txt) in enumerate(source_texts.items(), start=1):
        clipped = txt[:12000]
        numbered.append(f"[S{i}] id={sid}\n{clipped}")
        refs.append({"n": i, "id": sid, "chars": len(clipped)})
    context_block = "\n\n---\n\n".join(numbered) or "(no sources connected)"
    user = (f"CONNECTED SOURCES:\n{context_block}\n\n---\n\nTASK: {question}\n\n"
            f"Answer only from the sources above. Cite as [S1], [S2], ...")
    messages = [{"role": "system", "content": YAKU_SYSTEM}] + list(history or []) + [
        {"role": "user", "content": user}]
    r = PluginLlm(plugin_id="yaku-canvas").complete(messages, max_tokens=max_tokens, timeout=240)
    return {"answer": r.text, "sources": refs, "provider": r.provider, "model": r.model}


def _demo() -> None:  # pragma: no cover
    assert classify_url("https://youtu.be/dQw4w9WgXcQ")["kind"] == "youtube"
    assert _yt_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert _vtt_to_text("WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\nHello world\n") == "Hello world"
    b = {"id": "t", "name": "t", "nodes": [], "edges": []}
    save_board(b); assert load_board("t")["id"] == "t"
    print("service self-check OK")


if __name__ == "__main__":
    _demo()