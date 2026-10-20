# cherrycola

Local-model CLI for GraceOS. Runs inference through **Ollama** (default)
or **LM Studio's local server**. The GraceOS desktop calls it; users can too.

- Stdlib only (Python 3.12+). `pytest` is a test-only dependency.
- No AI, provider, or network needed to *run the tool itself* — but `ask`
  and `chat` need a local model server (Ollama or LM Studio) with a model.
- The Ollama server starts on demand (`ask`, `chat`, `pull`, `models`,
  `start`); never at boot.

## Install

Copy the package to `/usr/lib/cherrycola/` and the launcher to
`/usr/bin/cherrycola`:

```sh
sudo mkdir -p /usr/lib/cherrycola /usr/bin
sudo cp -r cherrycola /usr/lib/cherrycola/
sudo install -m755 bin/cherrycola /usr/bin/cherrycola
```

Or run from this directory with [uv](https://docs.astral.sh/uv/):

```sh
uv run cherrycola ask "hello"
uv run python -m cherrycola status
./bin/cherrycola status
```

## Config

`~/.config/grace/cherrycola.conf` (respects `$XDG_CONFIG_HOME`), simple
`key = value` lines with `#` comments. All optional:

| key | default | notes |
|---|---|---|
| `backend` | `auto` | `auto` = Ollama if the `ollama` command exists or its server answers, else LM Studio if its server answers |
| `model` | RAM-based | under 6 GB RAM → `qwen3:1.7b`, under 12 GB → `qwen3:4b`, else `qwen3:8b`; LM Studio defaults to its first listed model |
| `ollama_url` | `http://127.0.0.1:11434` | |
| `lmstudio_url` | `http://127.0.0.1:1234` | |
| `search` | `duckduckgo` | `duckduckgo` (default), `searxng`, or `off` |
| `searxng_url` | `http://127.0.0.1:8888` | base URL of a local SearXNG instance |
| `duckduckgo_url` | `https://html.duckduckgo.com/html/` | override for tests |
| `web_pages` | `3` | pages to read for `ask --web` (clamped 0..5) |

`cherrycola use MODEL` and `cherrycola backend NAME` rewrite only that one
line (comments and other lines kept; appended if absent).

## Usage

```sh
cherrycola ask "what is ext4?"          # one question, streamed
echo "summarize this" | cherrycola ask -   # question from stdin
cherrycola ask --show-thinking "why?"   # keep <think> blocks (stripped by default)
cherrycola ask --web "latest Arch news?"  # search the web, cite sources
cherrycola search "latest Arch news" [--json]  # web results, no model
cherrycola chat                         # interactive (/exit, /clear, /web, Ctrl+D)
cherrycola status [--json]
cherrycola models
cherrycola recommend [--json]           # models that fit this PC, and the Ollama build for its GPU
cherrycola pull [MODEL]                 # Ollama only; downloads from the internet
cherrycola use qwen3:4b
cherrycola backend lmstudio
cherrycola start                        # Ollama only
cherrycola stop                         # stops only the server cherrycola started
```

## `status --json` shape (stable)

```json
{"backend": "ollama", "configured_backend": "auto", "reachable": true, "model": "qwen3:4b",
 "installed": true, "running": "qwen3:4b", "models": ["qwen3:4b"], "search": "duckduckgo"}
```

`running` is `null` when no model is loaded. Exit 0 even when the server is
down (that is a status, not an error). Exit codes everywhere: 0 ok,
1 usage/other error, 2 backend unreachable, 3 model missing
(`ask`/`chat` when the model isn't downloaded — nothing is downloaded
without `pull`).

## How web search works

`cherrycola search` queries DuckDuckGo's HTML results (no key) or a
local SearXNG instance (`search = searxng`), then `ask --web` reads the
top `web_pages` pages locally and asks the model to answer from them,
with `[n]` citations and a `Sources:` list. Results and page text are
untrusted: the model only writes text, it never runs anything.
In `chat`, `/web` toggles web mode; history keeps only the question
and the answer, never the page text.

## Chat app

`cherrycola-chat` (CherryCola in the app grid) is a GTK4 / libadwaita window
on the same engine: pick the model in the header, turn on web search with the
globe, and old chats stay in the sidebar. A missing model shows a Download
banner. Chats are JSON files in `~/.local/share/cherrycola/chats/`; delete one
with the trash button. Needs `python-gobject` and `libadwaita`.

## Run the tests

Requires [uv](https://docs.astral.sh/uv/). From this directory:

```sh
uv run pytest -q
```

Tests spin up fake Ollama/LM Studio servers on localhost (port 0) — no
network, no real `ollama` process. The spawn function is injectable
(`start_server(cfg, spawn=...)`) and monkeypatched in tests.
