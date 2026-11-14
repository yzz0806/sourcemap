"""The polite fetch helper: robots.txt, per-host rate limit, back-off, raw bytes exactly as served.

Implements ADR 0008 (all network access by adapters goes through here) and is also used by
worker-side setup code such as the identifier checks. Uses only the standard library. The
transport, clock and sleep are injectable so tests never touch the network.
"""

import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlsplit

USER_AGENT = "sourcemap-bot/0.1 (research prototype)"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RawResponse:
    """What a server returned. `body` is the bytes exactly as served — never re-encoded."""

    url: str
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class BlockedByRobots(Exception):
    """The site's robots.txt disallows this URL for our user agent."""


class FetchError(Exception):
    """The fetch failed after all retries (network error or repeated 429/5xx)."""


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], RawResponse]


def urllib_transport(method: str, url: str, headers: Mapping[str, str], body: bytes | None,
                     timeout: float) -> RawResponse:
    """The real transport. HTTP error statuses are returned, not raised."""
    req = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return RawResponse(url=r.geturl(), status=r.status, headers=dict(r.headers.items()), body=r.read())
    except urllib.error.HTTPError as e:
        return RawResponse(url=url, status=e.code, headers=dict(e.headers.items()) if e.headers else {},
                           body=e.read() or b"")


class Kit:
    """Polite HTTP for one adapter call (or one setup task).

    - robots.txt is fetched once per host and obeyed (RFC 9309: 4xx → allowed; 5xx or unreachable →
      everything disallowed);
    - requests to one host are spaced by at least `min_interval_s`;
    - 429 and 5xx are retried with exponential back-off (1 s, 2 s, 4 s…) or `Retry-After`,
      up to `max_retries` attempts in total;
    - `key(name)` returns only keys this call was given (ADR 0008).
    """

    def __init__(self, *, transport: Transport = urllib_transport, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, min_interval_s: float = 1.0,
                 max_retries: int = 3, timeout_s: float = 30.0, keys: Mapping[str, str] | None = None,
                 user_agent: str = USER_AGENT):
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._min_interval = min_interval_s
        self._max_retries = max_retries
        self._timeout = timeout_s
        self._keys = dict(keys or {})
        self._ua = user_agent
        self._robots: dict[str, urllib.robotparser.RobotFileParser | bool] = {}
        self._last: dict[str, float] = {}

    # --- keys ---
    def key(self, name: str) -> str:
        if name not in self._keys:
            raise PermissionError(f"key {name} is not listed for this call")
        return self._keys[name]

    # --- requests ---
    def get(self, url: str, params: Mapping[str, str] | None = None,
            headers: Mapping[str, str] | None = None) -> RawResponse:
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urlencode(params)}"
        return self._request("GET", url, headers, None)

    def post(self, url: str, body: bytes, headers: Mapping[str, str] | None = None) -> RawResponse:
        return self._request("POST", url, headers, body)

    def __call__(self, url: str, **kw) -> RawResponse:
        """Shorthand for get(), so a Kit can be passed where a `fetch(url)` callable is expected."""
        return self.get(url, **kw)

    # --- internals ---
    def _host(self, url: str) -> str:
        p = urlsplit(url)
        return f"{p.scheme}://{p.netloc}"

    def _allowed(self, url: str) -> bool:
        host = self._host(url)
        if host not in self._robots:
            # RFC 9309: 4xx → no robots.txt, everything allowed; 5xx or unreachable → everything
            # disallowed (be conservative); 2xx → parse.
            r = self._send("GET", f"{host}/robots.txt", {}, None)
            if r is None or r.status >= 500:
                self._robots[host] = False
            elif r.status >= 400:
                self._robots[host] = True
            else:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(r.text().splitlines())
                self._robots[host] = parser
        rule = self._robots[host]
        if isinstance(rule, bool):
            return rule
        return rule.can_fetch(self._ua, url)

    def _wait_turn(self, url: str) -> None:
        host = self._host(url)
        last = self._last.get(host)
        if last is not None:
            wait = self._min_interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last[host] = self._clock()

    def _send(self, method, url, headers, body) -> RawResponse | None:
        self._wait_turn(url)
        h = {"User-Agent": self._ua, **(headers or {})}
        try:
            return self._transport(method, url, h, body, self._timeout)
        except OSError:
            return None

    def _request(self, method, url, headers, body) -> RawResponse:
        if not self._allowed(url):
            raise BlockedByRobots(url)
        last_status = None
        for attempt in range(self._max_retries):
            r = self._send(method, url, headers, body)
            if r is not None and r.status not in RETRY_STATUSES:
                return r
            last_status = None if r is None else r.status
            if attempt + 1 < self._max_retries:
                retry_after = r.headers.get("Retry-After") if r is not None else None
                delay = float(retry_after) if retry_after and retry_after.isdigit() else float(2 ** attempt)
                self._sleep(delay)
        raise FetchError(f"{method} {urlsplit(url).netloc}{urlsplit(url).path}: gave up after "
                         f"{self._max_retries} attempts (last status {last_status})")
