"""Record live API responses once, replay them in tests (no network, no keys needed).

Keys travel in headers, so the recorded URLs never contain secrets. Headers are not saved.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx


def _key(request: httpx.Request) -> str:
    u = urlsplit(str(request.url))
    q = urlencode(sorted(parse_qsl(u.query)))
    return f"{u.hostname}{u.path}?{q}"


class RecordingTransport(httpx.BaseTransport):
    """Passes requests through to the network and saves each 200 JSON response."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.tape = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.inner = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = self.inner.handle_request(request)
        resp.read()
        if resp.status_code == 200:
            self.tape[_key(request)] = resp.json()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.tape, indent=1), encoding="utf-8")
        # resp.content is already decompressed, so drop the encoding/length headers
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")}
        return httpx.Response(resp.status_code, content=resp.content, headers=headers)


class ReplayTransport(httpx.BaseTransport):
    """Serves saved responses; any request not on the tape gets a 404."""

    def __init__(self, path: Path):
        self.tape = json.loads(Path(path).read_text(encoding="utf-8"))
        self.seen: list[str] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        k = _key(request)
        self.seen.append(k)
        if k in self.tape:
            return httpx.Response(200, json=self.tape[k])
        return httpx.Response(404, json={"error": f"not on tape: {k}"})
