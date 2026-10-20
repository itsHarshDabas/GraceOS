"""CLI: ``cherrycola ask|chat|status|models|pull|use|backend|start|stop``."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

from . import backends as be
from . import config as config_mod
from . import hardware
from . import web as web_mod

__all__ = ["build_parser", "main", "run"]

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_UNREACHABLE = 2
EXIT_MODEL_MISSING = 3


def _err(message: str) -> None:
    print(f"CherryCola: {message}", file=sys.stderr)


def _state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "state")
    return Path(base) / "cherrycola"


def _runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base:
        return Path(base) / "cherrycola"
    return _state_dir()


def _pid_file() -> Path:
    return _runtime_dir() / "ollama.pid"


def _log_file() -> Path:
    return _state_dir() / "ollama.log"


def _read_pid() -> int | None:
    try:
        return int(_pid_file().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _is_ollama(pid: int) -> bool:
    """A stale pid file may point at a reused pid; only ever signal our ollama."""
    try:
        return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip() == "ollama"
    except OSError:
        return False


def _spawn(args: list[str], log_path: Path):
    """Spawn detached. Injectable seam: tests monkeypatch this."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "ab")
    try:
        proc = subprocess.Popen(
            args, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True,
        )
    finally:
        log.close()
    return proc


def start_server(cfg: config_mod.Config, spawn=_spawn,
                 timeout: float = 20) -> int:
    if be.server_reachable("ollama", cfg):
        return EXIT_OK
    if be.shutil.which("ollama") is None:
        _err("ollama is not installed, and its server is not running")
        return EXIT_UNREACHABLE
    log = _log_file()
    pid_path = _pid_file()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = spawn(["ollama", "serve"], log)
    except (OSError, be.BackendError) as exc:
        _err(f"could not start ollama: {exc}")
        return EXIT_UNREACHABLE
    try:
        pid_path.write_text(str(proc.pid) + "\n", encoding="utf-8")
    except OSError as exc:
        _err(f"could not write pid file: {exc}")
        return EXIT_UNREACHABLE
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if be.server_reachable("ollama", cfg):
            return EXIT_OK
        time.sleep(0.25)
    _err(f"ollama server did not start (see {log})")
    return EXIT_UNREACHABLE


def stop_server(cfg: config_mod.Config) -> int:
    _ = cfg
    pid = _read_pid()
    if pid is None:
        _err("cherrycola did not start an ollama server (no pid file)")
        return EXIT_UNREACHABLE
    if not _pid_alive(pid) or not _is_ollama(pid):
        try:
            _pid_file().unlink()
        except OSError:
            pass
        _err("cherrycola did not start an ollama server (not running)")
        return EXIT_UNREACHABLE
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        _err(f"could not stop ollama server (pid {pid}): {exc}")
        return EXIT_USAGE
    for _ in range(40):
        if not _pid_alive(pid):
            break
        time.sleep(0.25)
    try:
        _pid_file().unlink()
    except OSError:
        pass
    return EXIT_OK


def ensure_running(backend: str, cfg: config_mod.Config,
                   spawn=_spawn) -> int:
    """Start Ollama on demand. LM Studio has no local start path."""
    if backend != "ollama":
        if not be.server_reachable(backend, cfg):
            _err(f"lm studio server is not reachable at {cfg.lmstudio_url}")
            return EXIT_UNREACHABLE
        return EXIT_OK
    return start_server(cfg, spawn=spawn)


def _missing_model_message(model: str) -> str:
    size = config_mod.MODEL_SIZES_GB.get(model)
    if size is not None:
        return (
            f"the model {model} isn't downloaded yet "
            f"(about {size} GB). Run: cherrycola pull"
        )
    return f"the model {model} isn't downloaded yet. Run: cherrycola pull"


def _stream_answer(backend: str, cfg: config_mod.Config, model: str,
                   messages: list[dict[str, str]], show_thinking: bool) -> str:
    stripper = be.ThinkStripper(keep=show_thinking)
    full: list[str] = []
    for chunk in be.iter_chat_chunks(backend, cfg, model, messages):
        piece = stripper.feed(chunk)
        if piece:
            sys.stdout.write(piece)
            sys.stdout.flush()
            full.append(piece)
    tail = stripper.flush()
    if tail:
        sys.stdout.write(tail)
        sys.stdout.flush()
        full.append(tail)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return "".join(full)


def cmd_ask(args, cfg: config_mod.Config) -> int:
    backend = be.resolve_backend(cfg)
    rc = ensure_running(backend, cfg)
    if rc != EXIT_OK:
        return rc
    model = be.resolve_model(backend, cfg)
    if not be.check_model_installed(backend, model, cfg):
        _err(_missing_model_message(model))
        return EXIT_MODEL_MISSING
    if args.question == ["-"]:
        question = sys.stdin.read().strip()
    else:
        question = " ".join(args.question).strip()
    if not question:
        _err("ask needs a question")
        return EXIT_USAGE
    use_web = bool(getattr(args, "web", False))
    if use_web:
        return _answer_with_sources(question, args, cfg, backend, model)
    messages = [
        {"role": "system", "content": be.SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    try:
        _stream_answer(backend, cfg, model, messages, args.show_thinking)
    except be.BackendError as exc:
        _err(str(exc) or "backend request failed")
        return EXIT_UNREACHABLE
    except BrokenPipeError:
        return EXIT_OK
    return EXIT_OK


def _answer_with_sources(question: str, args, cfg: config_mod.Config,
                         backend: str, model: str,
                         history: list[dict[str, str]] | None = None) -> int:
    """Search, read the top pages, stream a cited answer, print Sources.

    history (chat) keeps only the plain question and answer; the page text
    goes in this turn's system prompt only.
    """
    if history is None:
        history = [{"role": "system", "content": be.SYSTEM_PROMPT}]
    try:
        results = web_mod.search(question, cfg)
        if not results:
            _err("web search returned nothing")
    except be.BackendError as exc:
        _err(str(exc) or "web search failed")
        results = []
    turn = {"role": "user", "content": question}
    if results:
        pages = web_mod.fetch_many([r.url for r in results[:cfg.web_pages]])
        grounded = web_mod.web_messages(question, results, pages)
        messages = grounded[:1] + history[1:] + [turn]
    else:
        _err("answering without the web")
        messages = history + [turn]
    try:
        answer = _stream_answer(backend, cfg, model, messages,
                                args.show_thinking)
    except be.BackendError as exc:
        _err(str(exc) or "backend request failed")
        return EXIT_UNREACHABLE
    except BrokenPipeError:
        return EXIT_OK
    history += [turn, {"role": "assistant", "content": answer}]
    if results:
        sys.stdout.write("\nSources:\n")
        for i, item in enumerate(results, start=1):
            sys.stdout.write(f"[{i}] {item.url}\n")
        sys.stdout.flush()
    return EXIT_OK


def cmd_search(args, cfg: config_mod.Config) -> int:
    query = " ".join(args.query).strip()
    if not query:
        _err("search needs a query")
        return EXIT_USAGE
    try:
        results = web_mod.search(query, cfg)
    except be.BackendError as exc:
        _err(str(exc) or "web search failed")
        return EXIT_UNREACHABLE
    if args.json:
        print(json.dumps([
            {"title": r.title, "url": r.url, "snippet": r.snippet}
            for r in results]))
        return EXIT_OK
    for i, item in enumerate(results, start=1):
        print(f"{i}. {item.title}")
        print(f"   {item.url}")
        print(f"   {item.snippet}")
    return EXIT_OK


def cmd_chat(args, cfg: config_mod.Config) -> int:
    backend = be.resolve_backend(cfg)
    rc = ensure_running(backend, cfg)
    if rc != EXIT_OK:
        return rc
    model = be.resolve_model(backend, cfg)
    if not be.check_model_installed(backend, model, cfg):
        _err(_missing_model_message(model))
        return EXIT_MODEL_MISSING
    history: list[dict[str, str]] = [
        {"role": "system", "content": be.SYSTEM_PROMPT}]
    web_mode = False
    print(f"CherryCola ({backend}/{model}). /exit quits, /clear resets.")
    while True:
        try:
            line = input("> ")
        except EOFError:
            print()
            return EXIT_OK
        except KeyboardInterrupt:
            print()
            return EXIT_OK
        text = line.strip()
        if not text:
            continue
        if text == "/exit":
            return EXIT_OK
        if text == "/clear":
            history = history[:1]
            print("(history cleared)")
            continue
        if text == "/web":
            web_mode = not web_mode
            print("Web search on." if web_mode else "Web search off.")
            continue
        if web_mode:
            _answer_with_sources(text, args, cfg, backend, model,
                                 history=history)
            continue
        history.append({"role": "user", "content": text})
        try:
            answer = _stream_answer(
                backend, cfg, model, history, args.show_thinking)
        except be.BackendError as exc:
            _err(str(exc) or "backend request failed")
            history.pop()
            continue
        except BrokenPipeError:
            return EXIT_OK
        history.append({"role": "assistant", "content": answer})


def cmd_status(args, cfg: config_mod.Config) -> int:
    backend = be.resolve_backend(cfg)
    reachable = be.server_reachable(backend, cfg)
    models: list[str] = []
    running: str | None = None
    if reachable:
        model = be.resolve_model(backend, cfg)
        try:
            models = be.list_models(backend, cfg)
        except be.BackendError:
            models = []
        installed = model in models
        running = be.running_model(backend, cfg)
    else:
        # Unreachable: no probing (would just time out); RAM default.
        model = cfg.model or config_mod.default_model_for_ram(
            config_mod.total_ram_bytes())
        installed = False
    if args.json:
        print(json.dumps({
            "backend": backend,
            "configured_backend": cfg.backend,
            "reachable": reachable,
            "model": model,
            "installed": installed,
            "running": running,
            "models": models,
            "search": cfg.search,
        }))
        return EXIT_OK
    print(f"backend:   {backend}")
    print(f"reachable: {'yes' if reachable else 'no'}")
    print(f"model:     {model}")
    print(f"installed: {'yes' if installed else 'no'}")
    print(f"running:   {running if running else '-'}")
    return EXIT_OK


def cmd_models(args, cfg: config_mod.Config) -> int:
    _ = args
    backend = be.resolve_backend(cfg)
    rc = ensure_running(backend, cfg)
    if rc != EXIT_OK:
        return rc
    try:
        models = be.list_models(backend, cfg)
    except be.BackendError as exc:
        _err(str(exc) or "could not list models")
        return EXIT_UNREACHABLE
    for name in models:
        print(name)
    return EXIT_OK


def cmd_recommend(args, cfg: config_mod.Config) -> int:
    _ = cfg
    r = hardware.recommend(config_mod.total_ram_bytes(),
                           hardware.detect_gpus())
    if args.json:
        print(json.dumps(r))
        return EXIT_OK
    where = (f"graphics card ({r['vram_gb']} GB)" if r["runs_on"] == "gpu"
             else f"processor ({r['ram_gb']} GB RAM)")
    print(f"Models run on the {where}.")
    state = ("installed" if r["engine_installed"]
             else f"install it: sudo pacman -S {r['engine']}")
    print(f"Engine: {r['engine']} - {r['engine_reason']} ({state})")
    print(f"Recommended: {r['recommended']}\n")
    for m in r["models"]:
        if m["fits"]:
            flag = "  (slow here)" if m["slow"] else ""
            print(f"  {m['model']:<20} {m['size_gb']:>5} GB  {m['note']}{flag}")
    return EXIT_OK


def cmd_pull(args, cfg: config_mod.Config) -> int:
    backend = be.resolve_backend(cfg)
    model = args.model or be.resolve_model(backend, cfg)
    if backend != "ollama":
        _err("models are downloaded in the LM Studio app")
        return EXIT_USAGE
    rc = ensure_running(backend, cfg)
    if rc != EXIT_OK:
        return rc
    print(f"Pulling {model} (downloads from the internet)...")

    def on_progress(obj: dict) -> None:
        total = obj.get("total")
        done = obj.get("completed")
        status = obj.get("status", "")
        if isinstance(total, (int, float)) and total and isinstance(
                done, (int, float)):
            pct = min(100.0, 100.0 * done / total)
            sys.stdout.write(f"\r{status} {pct:5.1f}%")
        else:
            sys.stdout.write(f"\r{status}".rstrip() + " " * 4)
        sys.stdout.flush()

    try:
        be.pull_model(backend, cfg, model, on_progress=on_progress)
    except be.BackendError as exc:
        sys.stdout.write("\n")
        _err(str(exc) or "pull failed")
        return EXIT_UNREACHABLE
    sys.stdout.write("\n")
    sys.stdout.flush()
    print(f"Pulled {model}.")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cherrycola", description="GraceOS local model CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="ask one question (streams the answer)")
    ask.add_argument("question", nargs="+", help="question words, or - for stdin")
    ask.add_argument("--show-thinking", action="store_true",
                     help="keep <think> reasoning blocks")
    ask.add_argument("--web", action="store_true",
                     help="search the web first and cite sources")

    search_cmd = sub.add_parser("search", help="search the web (no model)")
    search_cmd.add_argument("query", nargs="+", help="search words")
    search_cmd.add_argument("--json", action="store_true",
                            help="machine-readable JSON")

    chat = sub.add_parser("chat", help="interactive chat loop")
    chat.add_argument("--show-thinking", action="store_true",
                      help="keep <think> reasoning blocks")

    status = sub.add_parser("status", help="show backend/model status")
    status.add_argument("--json", action="store_true",
                        help="machine-readable JSON")

    sub.add_parser("models", help="list installed models")

    rec = sub.add_parser("recommend",
                         help="models and engine that suit this PC")
    rec.add_argument("--json", action="store_true",
                     help="machine-readable JSON")

    rm = sub.add_parser("remove", help="delete a downloaded model (Ollama only)")
    rm.add_argument("model")

    pull = sub.add_parser("pull", help="download a model (Ollama only)")
    pull.add_argument("model", nargs="?", default=None)

    use = sub.add_parser("use", help="set the default model")
    use.add_argument("model")

    bck = sub.add_parser("backend", help="set the backend")
    bck.add_argument("name", choices=["auto", "ollama", "lmstudio"])

    sub.add_parser("start", help="start the ollama server if needed")
    sub.add_parser("stop", help="stop the server cherrycola started")
    return parser


def run(argv: Sequence[str] | None = None,
        cfg: config_mod.Config | None = None) -> int:
    args = build_parser().parse_args(argv)
    loaded = cfg if cfg is not None else config_mod.load_config()
    try:
        if args.command == "ask":
            return cmd_ask(args, loaded)
        if args.command == "search":
            return cmd_search(args, loaded)
        if args.command == "chat":
            return cmd_chat(args, loaded)
        if args.command == "status":
            return cmd_status(args, loaded)
        if args.command == "models":
            return cmd_models(args, loaded)
        if args.command == "recommend":
            return cmd_recommend(args, loaded)
        if args.command == "pull":
            return cmd_pull(args, loaded)
        if args.command == "remove":
            backend = be.resolve_backend(loaded)
            rc = ensure_running(backend, loaded)
            if rc != EXIT_OK:
                return rc
            be.remove_model(backend, loaded, args.model)
            print(f"Removed {args.model}.")
            return EXIT_OK
        if args.command == "use":
            config_mod.save_setting("model", args.model, loaded.path)
            print(f"Using model {args.model}.")
            return EXIT_OK
        if args.command == "backend":
            config_mod.save_setting("backend", args.name, loaded.path)
            print(f"Using backend {args.name}.")
            return EXIT_OK
        if args.command == "start":
            if be.resolve_backend(loaded) != "ollama":
                _err("start only applies to the ollama backend")
                return EXIT_USAGE
            return start_server(loaded)
        if args.command == "stop":
            if be.resolve_backend(loaded) != "ollama":
                _err("stop only applies to the ollama backend")
                return EXIT_USAGE
            return stop_server(loaded)
    except be.BackendError as exc:
        _err(str(exc) or "backend request failed")
        return EXIT_UNREACHABLE
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return EXIT_USAGE
    return EXIT_USAGE  # pragma: no cover - argparse enforces the subcommand


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point (``[project.scripts]``)."""
    return run(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())





