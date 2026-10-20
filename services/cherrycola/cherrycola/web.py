"""Free web search for CherryCola: DuckDuckGo (default) or SearXNG.

Stdlib only. No API keys. Results and page text are untrusted text;
the model only writes text, it never runs anything.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import http.client
import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from . import backends as be
from .backends import BackendError

__all__ = [
    "BackendError",
    "Result",
    "fetch_many",
    "fetch_text",
    "search",
    "web_messages",
]

try:
    from . import __version__ as _version
except Exception:  # pragma: no cover - package metadata fallback
    _version = "0.0.0"

USER_AGENT = (
    f"CherryCola/{_version} (+https://github.com/itsHarshDabas/GraceOS)"
)

_SEARCH_TIMEOUT = 10
_FETCH_MAX_BYTES = 1_500_000
_SOURCE_BUDGET = 12_000

_SKIP_TAGS = frozenset({
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "form", "svg", "head",
})


@dataclass
class Result:
    title: str
    url: str
    snippet: str


def _user_agent() -> str:
    return USER_AGENT


def _one_line(text) -> str:
    return " ".join(str(text).split())


def _collapse(text: str) -> str:
    # Drop control characters too: titles end up on terminals.
    return " ".join("".join(
        c for c in text if c.isprintable() or c.isspace()).split())


def _truncate_words(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= 0:
        return ""
    cut = text[:max_chars].rstrip()
    space = cut.rfind(" ")
    if space > 0:
        return cut[:space]
    nxt = text.find(" ", max_chars)
    if nxt != -1:
        return text[:nxt]
    return text


def _decode_ddg_href(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    probe = href
    if probe.startswith("//"):
        probe = "https:" + probe
    try:
        parts = urllib.parse.urlparse(probe)
        query = urllib.parse.parse_qs(parts.query)
        uddg = query.get("uddg")
        if uddg and uddg[0]:
            return urllib.parse.unquote(uddg[0]).strip()
    except (ValueError, AttributeError):
        pass
    if href.startswith("//"):
        return ("https:" + href).strip()
    return href


def _is_http_url(url: str) -> bool:
    try:
        scheme = urllib.parse.urlparse(url).scheme.lower()
    except ValueError:
        return False
    return scheme in ("http", "https") and url.isprintable()

class _DDGParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[dict] = []
        self._results: list[dict] = []
        self._in_link = False
        self._link_result: dict | None = None
        self._snippet_result: dict | None = None
        self._snippet_tag: str | None = None
        self._snippet_depth = 0

    def _current_result(self) -> dict | None:
        for entry in reversed(self._stack):
            if entry["result"] is not None:
                return entry["result"]
        return None

    def handle_starttag(self, tag, attrs) -> None:
        tag = tag.lower()
        classes: list[str] = []
        href = ""
        for name, value in attrs:
            if name == "class" and value:
                classes = value.split()
            if name == "href" and value is not None:
                href = value
        result = None
        if tag == "div" and "result" in classes:
            is_ad = "result--ad" in classes
            result = {"is_ad": is_ad, "href": None,
                      "title": [], "snippet": []}
            self._results.append(result)
        self._stack.append({"tag": tag, "result": result})
        current = self._current_result()
        if tag == "a" and current is not None:
            if "result__a" in classes:
                if current["href"] is None:
                    current["href"] = href
                self._in_link = True
                self._link_result = current
        if "result__snippet" in classes and current is not None:
            if self._snippet_result is None:
                self._snippet_result = current
                self._snippet_tag = tag
                self._snippet_depth = len(self._stack)

    def handle_endtag(self, tag) -> None:
        tag = tag.lower()
        if tag == "a" and self._in_link:
            self._in_link = False
            self._link_result = None
        if self._snippet_result is not None:
            if self._snippet_tag == tag:
                if len(self._stack) <= self._snippet_depth:
                    self._snippet_result = None
                    self._snippet_tag = None
                    self._snippet_depth = 0
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data: str) -> None:
        if self._in_link and self._link_result is not None:
            self._link_result["title"].append(data)
        if self._snippet_result is not None:
            self._snippet_result["snippet"].append(data)

    def ordered(self) -> list[dict]:
        return list(self._results)


def _parse_ddg(html_text: str) -> list[Result]:
    parser = _DDGParser()
    parser.feed(html_text)
    parser.close()
    out: list[Result] = []
    seen: set[str] = set()
    for raw in parser.ordered():
        if raw.get("is_ad"):
            continue
        title = _collapse("".join(raw.get("title", [])))
        url = _decode_ddg_href(raw.get("href") or "")
        snippet = _collapse("".join(raw.get("snippet", [])))
        if not title or not url:
            continue
        if not _is_http_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(Result(title=title, url=url, snippet=snippet))
    return out

def _search_duckduckgo(query: str, cfg, max_results: int) -> list[Result]:
    base = (getattr(cfg, "duckduckgo_url", "") or "").rstrip("/")
    if not base:
        base = "https://html.duckduckgo.com/html"
    data = urllib.parse.urlencode({"q": query}).encode()
    req = urllib.request.Request(
        base, data=data,
        headers={"User-Agent": _user_agent(),
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_SEARCH_TIMEOUT) as resp:
            raw = resp.read(2_000_000)
    except Exception as exc:
        detail = _one_line(exc) or type(exc).__name__
        raise BackendError(f"duckduckgo search failed: {detail}") from exc
    try:
        results = _parse_ddg(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        detail = _one_line(exc) or type(exc).__name__
        raise BackendError(f"duckduckgo search failed: {detail}") from exc
    return results[:max(0, max_results)]


def _search_searxng(query: str, cfg, max_results: int) -> list[Result]:
    import json as _json

    base = (getattr(cfg, "searxng_url", "") or "").rstrip("/")
    url = base + "/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json"})
    req = urllib.request.Request(
        url, headers={"User-Agent": _user_agent()}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=_SEARCH_TIMEOUT) as resp:
            payload = _json.loads(resp.read(2_000_000).decode("utf-8"))
        items = payload.get("results", [])
        out: list[Result] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            title = _collapse(str(item.get("title", "")))
            page_url = str(item.get("url", "")).strip()
            snippet = _collapse(str(item.get("content", "")))
            if not title or not page_url:
                continue
            if not _is_http_url(page_url):
                continue
            if page_url in seen:
                continue
            seen.add(page_url)
            out.append(Result(title=title, url=page_url, snippet=snippet))
    except Exception as exc:
        detail = _one_line(exc) or type(exc).__name__
        raise BackendError(f"searxng search failed: {detail}") from exc
    return out[:max(0, max_results)]


def search(query, cfg, max_results: int = 5) -> list[Result]:
    """Web search. Raises BackendError on failure or when turned off."""
    backend = (getattr(cfg, "search", "duckduckgo") or "duckduckgo").strip()
    if backend == "off":
        raise BackendError(
            "web search is turned off (search = off in cherrycola.conf)")
    if backend == "searxng":
        return _search_searxng(query, cfg, max_results)
    return _search_duckduckgo(query, cfg, max_results)


_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_V4_COMPAT = ipaddress.ip_network("::/96")


def _public_ip(text: str) -> bool:
    try:
        ip = ipaddress.ip_address(text.split("%")[0])
    except ValueError:
        return False
    if ip.version == 6:  # IPv4 hidden in IPv6 counts as that IPv4
        if ip in _NAT64 or ip in _V4_COMPAT:
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        else:
            ip = ip.ipv4_mapped or ip.sixtofour or ip
    return ip.is_global and not ip.is_multicast


def _is_public_host(host: str) -> bool:
    """True only when host resolves to public internet addresses only."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, OSError, UnicodeError):
        return False
    return bool(infos) and all(_public_ip(i[4][0]) for i in infos)


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to another public http(s) host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlparse(newurl)
        if parts.scheme.lower() not in ("http", "https") or                 not _is_public_host(parts.hostname or ""):
            raise urllib.error.URLError("redirect to a non-public address")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _check_peer(conn) -> None:
    """Check the address actually connected to, so a host name can't
    switch to a local address after _is_public_host looked it up."""
    if not _is_public_host(conn.sock.getpeername()[0]):
        conn.sock.close()
        raise OSError("refusing to read a non-public address")


class _PublicHTTP(http.client.HTTPConnection):
    def connect(self):
        super().connect()
        _check_peer(self)


class _PublicHTTPS(http.client.HTTPSConnection):
    def connect(self):
        super().connect()
        _check_peer(self)


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_PublicHTTP, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_PublicHTTPS, req, context=self._context)


# shortcut: no proxy for page reads (the peer check would see the proxy),
# add proxy support with a CONNECT-aware check if someone needs it.
_opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({}), _HTTPHandler, _HTTPSHandler,
    _PublicRedirects)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._full: list[str] = []
        self._main: list[str] = []
        self._main_depth = 0

    def handle_starttag(self, tag, attrs) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "main" or tag == "article":
            self._main_depth += 1

    def handle_endtag(self, tag) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if tag == "main" or tag == "article":
            if self._main_depth > 0:
                self._main_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data
        if not text.strip():
            return
        self._full.append(text + " ")
        if self._main_depth:
            self._main.append(text + " ")

    def text(self) -> str:
        main_text = _collapse("".join(self._main))
        if main_text:
            return main_text
        return _collapse("".join(self._full))


def _extract_text(html_text: str) -> str:
    parser = _TextParser()
    parser.feed(html_text)
    parser.close()
    return parser.text()


def fetch_text(url: str, max_chars: int = 4000, timeout: float = 10) -> str:
    """Readable text of url. Returns "" when the page cannot be used."""
    try:
        parts = urllib.parse.urlparse((url or "").strip())
        if parts.scheme.lower() not in ("http", "https"):
            return ""
        host = parts.hostname or ""
        if not host:
            return ""
        if not _is_public_host(host):
            return ""
        req = urllib.request.Request(
            url, headers={"User-Agent": _user_agent()}, method="GET")
        with _opener.open(req, timeout=timeout) as resp:
            try:
                raw_ctype = resp.headers.get("Content-Type", "")
            except (AttributeError, ValueError):
                raw_ctype = ""
            ctype = (raw_ctype or "").split(";")[0].strip().lower()
            if ctype not in ("text/html", "text/plain"):
                return ""
            remaining = _FETCH_MAX_BYTES
            chunks: list[bytes] = []
            while remaining > 0:
                piece = resp.read(min(65536, remaining))
                if not piece:
                    break
                chunks.append(bytes(piece))
                remaining = remaining - len(piece)
            raw = b"".join(chunks).decode("utf-8", errors="replace")
        if ctype == "text/plain":
            return _truncate_words(_collapse(raw), max_chars)
        return _truncate_words(_extract_text(raw), max_chars)
    except Exception:
        return ""


def fetch_many(urls, max_chars: int = 4000) -> list[str]:
    """Fetch pages concurrently (max 3 workers), keeping input order."""
    items = list(urls or [])
    if not items:
        return []
    workers = max(1, min(3, len(items)))
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    with pool:
        return list(pool.map(lambda u: fetch_text(u, max_chars), items))


def web_messages(question, results, pages) -> list[dict]:
    """Chat messages grounding the model in web sources."""
    sources = list(results or [])
    given = list(pages or [])
    texts: list[str] = []
    for i, item in enumerate(sources):
        page = given[i] if i < len(given) and given[i] else ""
        if page:
            texts.append(page)
        else:
            texts.append(item.snippet or "")
    total = sum(len(t) for t in texts)
    while total > _SOURCE_BUDGET:
        longest = -1
        longest_len = 0
        for i, text in enumerate(texts):
            if len(text) > longest_len:
                longest_len = len(text)
                longest = i
        if longest < 0 or longest_len == 0:
            break
        target = longest_len - (total - _SOURCE_BUDGET)
        if target < 0:
            target = 0
        texts[longest] = _truncate_words(texts[longest], target)
        total = sum(len(t) for t in texts)
        if target == 0:
            break
    today = datetime.date.today().isoformat()
    lines: list[str] = [be.SYSTEM_PROMPT, "", "Web sources:"]
    for num, pair in enumerate(zip(sources, texts), start=1):
        item, text = pair
        lines.append("[%d] %s \u2014 %s" % (num, item.title, item.url))
        if text:
            lines.append(text)
        else:
            lines.append("(no text)")
        lines.append("")
    lines.append("Answer from these sources. Cite them like [1]. "
                 "If they don't answer the question, say so. "
                 "Today's date is %s." % today)
    system = "\n".join(lines).strip()
    return [{"role": "system", "content": system},
            {"role": "user", "content": question}]


