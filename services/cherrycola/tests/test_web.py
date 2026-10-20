"""Web search tests: fake DuckDuckGo / SearXNG / page servers."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from cherrycola import backends as be
from cherrycola import config as config_mod
from cherrycola import web as web_mod
from cherrycola.cli import run


DDG_HTML = """<html><body>
<div class="result result--ad">
<a class="result__a" href="https://ads.example/ad">Ad title</a>
<div class="result__snippet">Ad snippet here.</div>
</div>
<div class="result">
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fone&rut=abc">First result</a>
<div class="result__snippet">First snippet text.</div>
</div>
<div class="result">
<a class="result__a" href="https://example.com/two">Second result</a>
<div class="result__snippet">Second snippet text.</div>
</div>
<div class="result">
<a class="result__a" href="https://example.com/one">First result again</a>
<div class="result__snippet">Duplicate snippet.</div>
</div>
</body></html>"""


def _make_ddg_handler(page: str):
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        server_version = "CherryColaFakeDDG"

        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            seen["ua"] = self.headers.get("User-Agent", "")
            seen["body"] = body.decode()
            data = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    Handler.seen = seen
    return Handler


@pytest.fixture()
def ddg_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_ddg_handler(DDG_HTML))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield (f"http://127.0.0.1:{server.server_port}",
           server.RequestHandlerClass.seen)
    server.shutdown()
    thread.join()


@pytest.fixture()
def ddg_cfg(ddg_server, tmp_path):
    base, _seen = ddg_server
    path = tmp_path / "cherrycola.conf"
    return config_mod.Config(backend="ollama", model="qwen3:4b",
                             duckduckgo_url=base, path=path)


def test_ddg_parses_redirect_direct_and_duplicate(ddg_cfg, ddg_server):
    _base, seen = ddg_server
    results = web_mod.search("hello world", ddg_cfg)
    assert [(r.title, r.url, r.snippet) for r in results] == [
        ("First result", "https://example.com/one", "First snippet text."),
        ("Second result", "https://example.com/two", "Second snippet text."),
    ]
    assert "q=hello" in seen["body"]
    assert seen["ua"].startswith("CherryCola/")


def test_searxng_maps_json(tmp_path, monkeypatch):
    import urllib.request as urlreq

    payload = {"results": [
        {"title": "  S1 ", "url": "https://s.example/a",
         "content": "  snippet one  "},
        {"title": "S2", "url": "ftp://s.example/b", "content": "nope"},
    ]}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, n=-1):
            return json.dumps(payload).encode()

    calls = {}

    def fake_urlopen(req, timeout=None):
        calls["url"] = req.full_url
        calls["ua"] = req.get_header("User-agent")
        return FakeResp()

    monkeypatch.setattr(urlreq, "urlopen", fake_urlopen)
    cfg = config_mod.Config(search="searxng",
                            searxng_url="http://127.0.0.1:8888")
    results = web_mod.search("q", cfg)
    assert [(r.title, r.url, r.snippet) for r in results] == [
        ("S1", "https://s.example/a", "snippet one")]
    assert "format=json" in calls["url"]


PAGE_HTML = """<html><head><title>t</title><style>.x{}</style></head>
<body><nav>nav text</nav><script>var x = 1;</script>
<main><h1>Hello   world</h1><p>First para with words.</p>
<p>Second para here.</p></main>
<footer>foot</footer></body></html>"""


def _make_page_handler(page: bytes, ctype: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CherryColaFakePage"

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

    return Handler


@pytest.fixture()
def page_server():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        _make_page_handler(PAGE_HTML.encode(), "text/html; charset=utf-8"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join()


def test_fetch_text_prefers_main(page_server, monkeypatch):
    monkeypatch.setattr(web_mod, "_is_public_host", lambda host: True)
    url = page_server + "/p"
    full = web_mod.fetch_text(url, max_chars=4000)
    assert full == "Hello world First para with words. Second para here."
    assert "nav text" not in full
    assert "var x" not in full
    assert "foot" not in full
    short = web_mod.fetch_text(url, max_chars=20)
    assert short == "Hello world First"
    assert full.startswith(short)


def test_fetch_text_rejects_non_html(monkeypatch):
    import urllib.request as urlreq

    class FakeResp:
        headers = {"Content-Type": "application/pdf"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, n=-1):
            return b"%PDF-1.4 fake"

    class FakeOpener:
        def open(self, req, timeout=None):
            return FakeResp()

    monkeypatch.setattr(web_mod, "_opener", FakeOpener())
    monkeypatch.setattr(web_mod, "_is_public_host", lambda host: True)
    assert web_mod.fetch_text("http://example.com/f.pdf") == ""


def test_fetch_text_refuses_redirect_to_private_host(monkeypatch):
    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(302)
            self.send_header(
                "Location", f"http://localhost:{self.server.server_port}/in")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # 127.0.0.1 counts as public here, localhost doesn't.
        monkeypatch.setattr(web_mod, "_is_public_host",
                            lambda host: host == "127.0.0.1")
        url = f"http://127.0.0.1:{server.server_port}/out"
        assert web_mod.fetch_text(url) == ""
    finally:
        server.shutdown()
        thread.join()


def test_fetch_text_refuses_private_host():
    assert web_mod.fetch_text("http://127.0.0.1:9/nope") == ""
    assert web_mod._is_public_host("127.0.0.1") is False


def test_ask_web_end_to_end(ollama_cfg, capsys, monkeypatch):
    import urllib.request as urlreq

    real_urlopen = urlreq.urlopen
    chat_payloads = []

    class ChatReader:
        def __init__(self, resp):
            self._resp = resp

        def __enter__(self):
            return self._resp.__enter__()

        def __exit__(self, *args):
            return self._resp.__exit__(*args)

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if url.endswith("/api/chat"):
            chat_payloads.append(json.loads(req.data.decode()))
            return ChatReader(real_urlopen(req, timeout=timeout))
        return real_urlopen(req, timeout=timeout)

    monkeypatch.setattr(urlreq, "urlopen", fake_urlopen)
    monkeypatch.setattr(web_mod, "_is_public_host", lambda host: True)
    ollama_cfg.web_pages = 3

    def fake_search(query, cfg, max_results=5):
        return [web_mod.Result(title="T1", url="http://example.com/page",
                               snippet="snip one")]

    monkeypatch.setattr(web_mod, "search", fake_search)

    def fake_fetch(urls, max_chars=4000):
        assert urls == ["http://example.com/page"]
        return ["PAGE BODY TEXT HERE"]

    monkeypatch.setattr(web_mod, "fetch_many", fake_fetch)

    assert run(["ask", "--web", "what is up?"], cfg=ollama_cfg) == 0
    out = capsys.readouterr().out
    assert "PAGE BODY TEXT HERE" in chat_payloads[0]["messages"][0]["content"]
    assert "[1]" in chat_payloads[0]["messages"][0]["content"]
    assert out.rstrip().endswith("Sources:\n[1] http://example.com/page")


def test_ask_web_search_off_still_answers(ollama_cfg, capsys):
    ollama_cfg.search = "off"
    assert run(["ask", "--web", "hello"], cfg=ollama_cfg) == 0
    out = capsys.readouterr()
    assert out.out == "Hello world!\n"
    assert "turned off" in out.err
    assert "answering without the web" in out.err


def test_chat_web_toggle(ollama_cfg, capsys, monkeypatch):
    from cherrycola import cli as cli_mod

    answers = iter(["/web", "hi there", "/web", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(
        web_mod, "search",
        lambda q, cfg, max_results=5: [
            web_mod.Result(title="T", url="http://example.com/x",
                           snippet="s")])
    monkeypatch.setattr(web_mod, "fetch_many",
                        lambda urls, max_chars=4000: ["p"])
    args = cli_mod.build_parser().parse_args(["chat"])
    assert cli_mod.cmd_chat(args, ollama_cfg) == 0
    out = capsys.readouterr().out
    assert "Web search on." in out
    assert "Web search off." in out
    assert out.count("Hello world!") == 1
    assert "[1] http://example.com/x" in out


def test_status_json_includes_search(ollama_cfg, capsys):
    assert run(["status", "--json"], cfg=ollama_cfg) == 0
    assert json.loads(capsys.readouterr().out)["search"] == "duckduckgo"


def test_search_command_and_json(ollama_cfg, capsys, monkeypatch):
    monkeypatch.setattr(
        web_mod, "search",
        lambda q, cfg, max_results=5: [
            web_mod.Result(title="T", url="http://example.com/x",
                           snippet="snip")])
    assert run(["search", "hello"], cfg=ollama_cfg) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == ["1. T", "   http://example.com/x", "   snip"]
    assert run(["search", "hello", "--json"], cfg=ollama_cfg) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == [{"title": "T", "url": "http://example.com/x",
                        "snippet": "snip"}]


def test_search_failure_exit_2(ollama_cfg, capsys, monkeypatch):
    def boom(query, cfg, max_results=5):
        raise be.BackendError("duckduckgo search failed: down")

    monkeypatch.setattr(web_mod, "search", boom)
    assert run(["search", "hello"], cfg=ollama_cfg) == 2
    assert "down" in capsys.readouterr().err


def test_search_config_keys_and_clamping(tmp_path):
    path = tmp_path / "c.conf"
    path.write_text("search = searxng\nsearxng_url = http://x:8888/\n"
                    "duckduckgo_url = http://y/html/\nweb_pages = 9\n",
                    encoding="utf-8")
    cfg = config_mod.load_config(path)
    assert cfg.search == "searxng"
    assert cfg.searxng_url == "http://x:8888"
    assert cfg.duckduckgo_url == "http://y/html"
    assert cfg.web_pages == 5
    path.write_text("web_pages = -3\nsearch = bogus\n", encoding="utf-8")
    cfg = config_mod.load_config(path)
    assert cfg.web_pages == 0
    assert cfg.search == "duckduckgo"


def test_web_messages_budget_and_format():
    import datetime as dt_mod

    today = dt_mod.date.today().isoformat()
    results = [web_mod.Result(title="A", url="http://a.example", snippet="s"),
               web_mod.Result(title="B", url="http://b.example", snippet="t")]
    long_page = "word " * 4000
    messages = web_mod.web_messages("Q?", results, [long_page, "short"])
    assert len(messages) == 2
    assert messages[1] == {"role": "user", "content": "Q?"}
    system = messages[0]["content"]
    assert system.startswith(be.SYSTEM_PROMPT)
    assert "[1] A \u2014 http://a.example" in system
    assert "[2] B \u2014 http://b.example" in system
    assert "Cite them like [1]" in system
    assert today in system
    assert len(system) < 20000


def test_chat_web_turn_keeps_history(ollama_cfg, capsys, monkeypatch):
    from cherrycola import backends as be
    from cherrycola import cli as cli_mod

    sent = []

    def fake_chunks(backend, cfg, model, messages):
        sent.append(messages)
        yield "ok"

    monkeypatch.setattr(be, "iter_chat_chunks", fake_chunks)
    answers = iter(["first", "/web", "second", "/exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(
        web_mod, "search",
        lambda q, cfg, max_results=5: [
            web_mod.Result(title="T", url="http://example.com/x",
                           snippet="s")])
    monkeypatch.setattr(web_mod, "fetch_many",
                        lambda urls, max_chars=4000: ["PAGE"])
    args = cli_mod.build_parser().parse_args(["chat"])
    assert cli_mod.cmd_chat(args, ollama_cfg) == 0
    web_turn = sent[1]
    assert [m["role"] for m in web_turn] == [
        "system", "user", "assistant", "user"]
    assert "PAGE" in web_turn[0]["content"]
    assert [m["content"] for m in web_turn[1:]] == ["first", "ok", "second"]
