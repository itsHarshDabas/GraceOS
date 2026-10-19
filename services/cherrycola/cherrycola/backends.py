"""HTTP backends: Ollama and LM Studio (OpenAI-compatible). Stdlib only."""

from __future__ import annotations

import http.client
import json
import shutil
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import config as config_mod

__all__ = [
    "BackendError",
    "BackendResult",
    "ThinkStripper",
    "check_model_installed",
    "detect_backend",
    "http_get_json",
    "iter_chat_chunks",
    "list_models",
    "pull_model",
    "resolve_backend",
    "resolve_model",
    "running_model",
    "server_reachable",
]

_TIMEOUT = 10

SYSTEM_PROMPT = (
    "You are CherryCola, the local assistant built into GraceOS. "
    "Answer briefly and plainly."
)


class BackendError(Exception):
    """Expected backend failure (server down, HTTP error, bad payload)."""


@dataclass
class BackendResult:
    backend: str
    reachable: bool


class ThinkStripper:
    """Strip <think>...</think> from a stream, chunk by chunk.

    Tags may split across chunks, so hold a small tail buffer and only
    emit text once it cannot become part of a tag.
    """

    def __init__(self, keep: bool = False) -> None:
        self.keep = keep
        self._buf = ""
        self._in_think = False

    def feed(self, chunk: str) -> str:
        if self.keep:
            return chunk
        self._buf += chunk
        out: list[str] = []
        while True:
            if self._in_think:
                end = self._buf.find("</think>")
                if end == -1:
                    tail = len("</think>") - 1
                    if len(self._buf) > tail:
                        self._buf = self._buf[-tail:]
                    break
                self._buf = self._buf[end + len("</think>"):]
                self._in_think = False
                continue
            start = self._buf.find("<think>")
            if start == -1:
                # Hold back any tail that could start a tag.
                held = ""
                for tag in ("<think>", "</think>"):
                    for n in range(min(len(self._buf), len(tag) - 1), 0, -1):
                        if tag.startswith(self._buf[-n:]):
                            if len(self._buf[-n:]) > len(held):
                                held = self._buf[-n:]
                if held:
                    cut = len(self._buf) - len(held)
                    out.append(self._buf[:cut])
                    self._buf = held
                    break
                # A lone trailing "<" could also start a tag.
                if self._buf.endswith("<"):
                    out.append(self._buf[:-1])
                    self._buf = "<"
                    break
                out.append(self._buf)
                self._buf = ""
                break
            # Found "<think>": emit text before it, enter thinking.
            head = self._buf[:start]
            # Keep a trailing "<" of head? No: "<think>" matched fully,
            # so head is safe to emit.
            out.append(head)
            self._buf = self._buf[start + len("<think>"):]
            self._in_think = True
        return "".join(out)

    def flush(self) -> str:
        if self.keep:
            rest, self._buf = self._buf, ""
            return rest
        if self._in_think:
            self._buf = ""
            self._in_think = False
            return ""
        rest, self._buf = self._buf, ""
        return rest


def _url(base: str, path: str) -> str:
    return base.rstrip("/") + path


def http_get_json(url: str, timeout: float = _TIMEOUT) -> object:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, socket.timeout, OSError,
            http.client.HTTPException, ValueError) as exc:
        raise BackendError(str(exc) or type(exc).__name__) from exc


def server_reachable(backend: str, cfg: config_mod.Config) -> bool:
    base = cfg.ollama_url if backend == "ollama" else cfg.lmstudio_url
    probe = "/api/version" if backend == "ollama" else "/v1/models"
    try:
        http_get_json(_url(base, probe), timeout=3)
    except BackendError:
        return False
    return True


def detect_backend(cfg: config_mod.Config) -> str:
    """auto: Ollama if the CLI exists or its server answers, else LM Studio."""
    if shutil.which("ollama") is not None:
        return "ollama"
    if server_reachable("ollama", cfg):
        return "ollama"
    if server_reachable("lmstudio", cfg):
        return "lmstudio"
    return "ollama"


def resolve_backend(cfg: config_mod.Config) -> str:
    if cfg.backend == "auto":
        return detect_backend(cfg)
    return cfg.backend


def resolve_model(backend: str, cfg: config_mod.Config) -> str:
    if cfg.model:
        return cfg.model
    if backend == "lmstudio":
        try:
            models = list_models("lmstudio", cfg)
        except BackendError:
            models = []
        if models:
            return models[0]
    return config_mod.default_model_for_ram(config_mod.total_ram_bytes())


def list_models(backend: str, cfg: config_mod.Config) -> list[str]:
    if backend == "ollama":
        try:
            payload = http_get_json(_url(cfg.ollama_url, "/api/tags"))
        except BackendError as exc:
            raise BackendError(f"ollama server not reachable: {exc}") from exc
        try:
            return [m["name"] for m in payload["models"]]  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise BackendError(
                f"bad response from {cfg.ollama_url}/api/tags") from exc
    try:
        payload = http_get_json(_url(cfg.lmstudio_url, "/v1/models"))
    except BackendError as exc:
        raise BackendError(f"lm studio server not reachable: {exc}") from exc
    try:
        return [m["id"] for m in payload["data"]]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise BackendError(
            f"bad response from {cfg.lmstudio_url}/v1/models") from exc


def running_model(backend: str, cfg: config_mod.Config) -> str | None:
    if backend == "ollama":
        try:
            payload = http_get_json(_url(cfg.ollama_url, "/api/ps"))
        except BackendError:
            return None
        try:
            models = payload["models"]  # type: ignore[index]
            if models:
                return models[0]["name"]  # type: ignore[index]
        except (KeyError, TypeError, IndexError):
            return None
        return None
    try:
        models = list_models("lmstudio", cfg)
    except BackendError:
        return None
    return models[0] if models else None


def check_model_installed(backend: str, model: str,
                          cfg: config_mod.Config) -> bool:
    try:
        return model in list_models(backend, cfg)
    except BackendError:
        return False


def _open_chat_stream(backend: str, cfg: config_mod.Config,
                      model: str, messages: list[dict[str, str]]):
    if backend == "ollama":
        url = _url(cfg.ollama_url, "/api/chat")
    else:
        url = _url(cfg.lmstudio_url, "/v1/chat/completions")
    data = json.dumps(
        {"model": model, "messages": messages, "stream": True}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # Loading a model on a slow CPU can take minutes before the first byte.
        return urllib.request.urlopen(req, timeout=600)
    except (urllib.error.URLError, socket.timeout, OSError,
            http.client.HTTPException) as exc:
        raise BackendError(str(exc) or type(exc).__name__) from exc


def _iter_ollama_text(resp):
    buf = b""
    for raw in resp:
        buf += bytes(raw)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line.decode("utf-8"))
            except ValueError:
                continue
            if obj.get("error"):
                raise BackendError(str(obj["error"]))
            content = obj.get("message", {}).get("content", "")
            if content:
                yield content
            if obj.get("done"):
                return
    if buf.strip():
        try:
            obj = json.loads(buf.strip().decode("utf-8"))
        except ValueError:
            return
        content = obj.get("message", {}).get("content", "")
        if content:
            yield content


def _iter_lmstudio_text(resp):
    buf = ""
    for raw in resp:
        buf += bytes(raw).decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                return
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            if obj.get("error"):
                err = obj["error"]
                msg = err.get("message", err) if isinstance(err, dict) else err
                raise BackendError(str(msg))
            try:
                delta = obj["choices"][0]["delta"].get("content", "")
            except (KeyError, TypeError, IndexError):
                continue
            if delta:
                yield delta


def iter_chat_chunks(backend, cfg, model, messages):
    """Yield text chunks from a streaming chat request."""
    with _open_chat_stream(backend, cfg, model, messages) as resp:
        if backend == "ollama":
            yield from _iter_ollama_text(resp)
        else:
            yield from _iter_lmstudio_text(resp)


def pull_model(backend, cfg, model, on_progress=None) -> None:
    """Ollama only: POST /api/pull, streaming progress objects."""
    if backend != "ollama":
        raise BackendError("models are downloaded in the LM Studio app")
    url = _url(cfg.ollama_url, "/api/pull")
    data = json.dumps({"model": model, "stream": True}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=3600)
    except (urllib.error.URLError, socket.timeout, OSError,
            http.client.HTTPException) as exc:
        raise BackendError(str(exc) or type(exc).__name__) from exc
    with resp:
        buf = b""
        for raw in resp:
            buf += bytes(raw)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line.decode("utf-8"))
                except ValueError:
                    continue
                if obj.get("error"):
                    raise BackendError(str(obj["error"]))
                if on_progress is not None:
                    on_progress(obj)



