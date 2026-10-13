# Yaku Canvas — Hermes Desktop Plugin

An infinite canvas for content research, rebuilt from the Yaku desktop app
(getyaku.com) by REA and shipped as a Hermes Desktop plugin.

Sources (YouTube / TikTok / Reddit / web links, plain notes) become cards on a
board. Wire cards into **✨ Yaku Chat** and it writes scripts/posts grounded
**only** in the connected sources, citing each one it used.

## What's in the package

| Half | What it is |
|---|---|
| Agent (Python) | `yaku_add_source` / `yaku_list_sources` / `yaku_chat` tools the agent can drive; service with Yaku's recovered fetch chain; dashboard REST backend |
| Desktop (JS) | `/yaku` tab in Hermes Desktop: draggable canvas, note cards, inline editing, wire connect/cut, grounded composer |

## Install

Hermes Desktop → plugin manager → **Install from Git** →

```
https://github.com/Gabebac/hermes-yaku-canvas
```

Check the **Desktop** target. The desktop half needs to land on the machine the
app runs on — that's what this flow does.

The agent half runs on the Hermes backend: `hermes plugins enable yaku-canvas`
(or it installs alongside).

## Use

1. Open the **Yaku Canvas** tab (sidebar, or ⌘K → "Open Yaku Canvas")
2. Paste a video/social/web link → card appears with its transcript/text fetched
3. Or **+ Note** to write your own angle/hook/brief
4. **Connect** cards (or drag) into the chat node
5. Ask → grounded answer with `[S1]`-style citations

Both you and the agent edit the same board; cards sync through the plugin's
backend store.