"""The polite fetch helper — sandbox.kit (ADR 0008): robots.txt, rate limit, back-off, raw bytes."""

import pytest

from sourcemap.sandbox.kit import BlockedByRobots, FetchError, Kit, RawResponse


class FakeTransport:
    """Programmed responses per URL; records the times requests were made."""

    def __init__(self, routes, clock):
        self.routes = routes
        self.clock = clock
        self.log = []

    def __call__(self, method, url, headers, body, timeout):
        self.log.append((self.clock.t, url))
        r = self.routes.get(url)
        if callable(r):
            r = r()
        if r is None:
            return RawResponse(url=url, status=404, headers={}, body=b"")
        status, body = r
        return RawResponse(url=url, status=status, headers={"content-type": "text/html"}, body=body)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def make(routes, **kw):
    clock = FakeClock()
    transport = FakeTransport(routes, clock)
    kit = Kit(transport=transport, clock=clock.now, sleep=clock.sleep, **kw)
    return kit, transport, clock


ROBOTS_OK = (200, b"User-agent: *\nDisallow: /private\n")


def test_bytes_are_returned_exactly_as_served():
    body = b"<html>\xe2\x80\x94 Airtable</html>"
    kit, _, _ = make({"https://a.com/robots.txt": ROBOTS_OK, "https://a.com/team": (200, body)})
    r = kit.get("https://a.com/team")
    assert r.status == 200 and r.body == body


def test_robots_disallowed_page_is_blocked():
    kit, t, _ = make({"https://a.com/robots.txt": ROBOTS_OK, "https://a.com/private/x": (200, b"secret")})
    with pytest.raises(BlockedByRobots):
        kit.get("https://a.com/private/x")
    assert all("private" not in url for _, url in t.log)


def test_missing_robots_txt_allows():
    kit, _, _ = make({"https://a.com/team": (200, b"ok")})
    assert kit.get("https://a.com/team").status == 200


def test_requests_to_one_host_are_spaced():
    kit, t, _ = make({"https://a.com/robots.txt": ROBOTS_OK, "https://a.com/1": (200, b""),
                      "https://a.com/2": (200, b"")}, min_interval_s=2.0)
    kit.get("https://a.com/1")
    kit.get("https://a.com/2")
    page_times = [ts for ts, url in t.log if "robots" not in url]
    assert page_times[1] - page_times[0] >= 2.0


def test_back_off_on_429_then_success():
    answers = iter([(429, b""), (503, b""), (200, b"ok")])
    kit, t, clock = make({"https://a.com/robots.txt": ROBOTS_OK, "https://a.com/x": lambda: next(answers)},
                         max_retries=3)
    r = kit.get("https://a.com/x")
    assert r.status == 200
    assert len([1 for _, url in t.log if url.endswith("/x")]) == 3
    assert clock.t >= 3.0  # waited 1 s then 2 s


def test_gives_up_after_max_retries():
    kit, _, _ = make({"https://a.com/robots.txt": ROBOTS_OK, "https://a.com/x": (429, b"")}, max_retries=2)
    with pytest.raises(FetchError):
        kit.get("https://a.com/x")


def test_keys_only_listed_ones():
    kit, _, _ = make({}, keys={"OPENDART_API_KEY": "k"})
    assert kit.key("OPENDART_API_KEY") == "k"
    with pytest.raises(PermissionError):
        kit.key("APIFY_TOKEN")


def test_robots_txt_4xx_means_allowed_rfc9309():
    """api.ror.org answers robots.txt with 403; RFC 9309 treats any 4xx as 'no robots.txt'."""
    kit, _, _ = make({"https://a.com/robots.txt": (403, b"{}"), "https://a.com/x": (200, b"ok")})
    assert kit.get("https://a.com/x").status == 200


def test_robots_txt_5xx_means_everything_disallowed_rfc9309():
    kit, t, _ = make({"https://a.com/robots.txt": (503, b""), "https://a.com/x": (200, b"ok")}, max_retries=1)
    with pytest.raises(BlockedByRobots):
        kit.get("https://a.com/x")
    assert all(not url.endswith("/x") for _, url in t.log)
