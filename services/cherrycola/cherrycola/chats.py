"""Saved conversations for the CherryCola chat app, one JSON file per chat.

Stored in $XDG_DATA_HOME/cherrycola/chats (default ~/.local/share). Kept free
of GTK so it can be tested anywhere.
"""

from __future__ import annotations

import html
import json
import os
import re
import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import backends as be

_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")


@dataclass
class Chat:
    id: str
    model: str
    title: str = "New chat"
    # {"role": "user"|"assistant", "content": str, "sources": [url, ...]}
    messages: list[dict] = field(default_factory=list)
    updated: float = 0.0


def chats_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
        "~/.local/share")
    return Path(base) / "cherrycola" / "chats"


def new_chat(model: str) -> Chat:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Chat(id=f"{stamp}-{secrets.token_hex(2)}", model=model,
                updated=time.time())


def _path(chat_id: str, d: Path | None) -> Path:
    if not _ID.match(chat_id):
        raise ValueError(f"bad chat id: {chat_id!r}")
    return (d or chats_dir()) / f"{chat_id}.json"


def save(chat: Chat, d: Path | None = None) -> None:
    path = _path(chat.id, d)
    path.parent.mkdir(parents=True, exist_ok=True)
    chat.updated = time.time()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(chat), ensure_ascii=False),
                   encoding="utf-8")
    os.replace(tmp, path)


def load(chat_id: str, d: Path | None = None) -> Chat:
    data = json.loads(_path(chat_id, d).read_text(encoding="utf-8"))
    return Chat(id=chat_id, model=str(data.get("model", "")),
                title=str(data.get("title", "New chat")),
                messages=list(data.get("messages", [])),
                updated=float(data.get("updated", 0)))


def list_chats(d: Path | None = None) -> list[Chat]:
    """All saved chats, newest first. Unreadable files are skipped."""
    d = d or chats_dir()
    out = []
    for path in d.glob("*.json") if d.is_dir() else []:
        try:
            out.append(load(path.stem, d))
        except (OSError, ValueError, TypeError):
            continue
    return sorted(out, key=lambda c: c.updated, reverse=True)


def delete(chat_id: str, d: Path | None = None) -> None:
    try:
        _path(chat_id, d).unlink()
    except FileNotFoundError:
        pass


def title_for(question: str, limit: int = 40) -> str:
    line = " ".join(question.split())
    if len(line) <= limit:
        return line or "New chat"
    cut = line[:limit].rsplit(" ", 1)[0] or line[:limit]
    return cut + "…"


def model_messages(chat: Chat) -> list[dict[str, str]]:
    """What the model sees: the system prompt and the plain turns."""
    return [{"role": "system", "content": be.SYSTEM_PROMPT}] + [
        {"role": m["role"], "content": m["content"]} for m in chat.messages]


def to_markup(text: str) -> str:
    """A little Markdown to Pango markup: ``` blocks, `code`, **bold**."""
    out = []
    for i, part in enumerate(text.split("```")):
        if i % 2:  # inside a fenced block; drop the language tag line
            first, _, rest = part.partition("\n")
            body = rest if first.strip() and " " not in first.strip() else part
            out.append(f"<tt>{html.escape(body.strip(chr(10)), quote=False)}</tt>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"`([^`\n]+)`", r"<tt>\1</tt>", s)
        s = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?m)^#{1,6} +(.+)$", r"<b>\1</b>", s)
        out.append(s)
    return "".join(out)
