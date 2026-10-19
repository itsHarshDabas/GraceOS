"""Config: ~/.config/grace/cherrycola.conf (key = value, # comments)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BACKENDS",
    "DEFAULT_LMSTUDIO_URL",
    "DEFAULT_OLLAMA_URL",
    "MODEL_SIZES_GB",
    "Config",
    "config_path",
    "default_model_for_ram",
    "load_config",
    "save_setting",
    "total_ram_bytes",
]

BACKENDS = ("auto", "ollama", "lmstudio")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_LMSTUDIO_URL = "http://127.0.0.1:1234"

#: Approximate download sizes for the default models (GB).
MODEL_SIZES_GB = {
    "qwen3:1.7b": 1.4,
    "qwen3:4b": 2.6,
    "qwen3:8b": 5.2,
}

_VALID_KEYS = ("backend", "model", "ollama_url", "lmstudio_url")


@dataclass
class Config:
    backend: str = "auto"
    model: str | None = None
    ollama_url: str = DEFAULT_OLLAMA_URL
    lmstudio_url: str = DEFAULT_LMSTUDIO_URL
    path: Path | None = None


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return Path(base) / "grace" / "cherrycola.conf"


def load_config(path: Path | None = None) -> Config:
    cfg = Config(path=path or config_path())
    try:
        text = cfg.path.read_text(encoding="utf-8")  # type: ignore[union-attr]
    except FileNotFoundError:
        return cfg
    except OSError:
        return cfg
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key not in _VALID_KEYS or not value:
            continue
        if key == "backend":
            if value in BACKENDS:
                cfg.backend = value
        elif key == "model":
            cfg.model = value
        elif key == "ollama_url":
            cfg.ollama_url = value.rstrip("/")
        elif key == "lmstudio_url":
            cfg.lmstudio_url = value.rstrip("/")
    return cfg


def save_setting(key: str, value: str, path: Path | None = None) -> Path:
    """Rewrite one ``key = value`` line, keeping comments; append if absent."""
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
        had_file = True
    except FileNotFoundError:
        lines = []
        had_file = False
    prefix = key.strip() + "="
    squished = key.strip()
    updated = False
    out: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if (
            not updated
            and stripped
            and not stripped.startswith("#")
            and "=" in raw
        ):
            k, _, _ = raw.partition("=")
            if k.strip() == squished:
                out.append(f"{squished} = {value}")
                updated = True
                continue
        out.append(raw)
    _ = prefix  # documented: match is on the key part before '='
    if not updated:
        out.append(f"{squished} = {value}")
    text = "\n".join(out) + "\n"
    if had_file or out:
        target.write_text(text, encoding="utf-8")
    return target


def total_ram_bytes(meminfo: str = "/proc/meminfo") -> int | None:
    try:
        with open(meminfo, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    parts = line.split()
                    return int(parts[1]) * 1024  # kB -> bytes
    except (OSError, ValueError, IndexError):
        return None
    return None


def default_model_for_ram(total_bytes: int | None) -> str:
    if total_bytes is None:
        return "qwen3:4b"
    gb = total_bytes / 1024**3
    if gb < 6:
        return "qwen3:1.7b"
    if gb < 12:
        return "qwen3:4b"
    return "qwen3:8b"
