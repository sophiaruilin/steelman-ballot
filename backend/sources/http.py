"""Shared, locked-down HTTP client for every source adapter.

Safety rules enforced here (Security section of the plan):
  * HTTPS only, and only hosts on ALLOWED_HOSTS (no SSRF to internal addresses).
  * API keys travel in request headers, never in URLs, so they can't leak into
    error messages, logs or citations.
  * One retry with backoff on 429 / 5xx; a short, fixed timeout.
  * Every successful call returns a SourceRecord: the data plus the citation
    (public URL), the time it was fetched, and a fingerprint for the cache's
    change detection.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from backend import config

ALLOWED_HOSTS = {
    "geocoding.geo.census.gov",
    "api.census.gov",
    "api.open.fec.gov",
    "api.congress.gov",
    "v3.openstates.org",
    "api.votesmart.org",
}


class SourceError(RuntimeError):
    """A source could not be reached or refused the request. Message never contains keys."""


class BlockedURL(SourceError):
    """The URL is not HTTPS or its host is not on the allowlist."""


@dataclass
class SourceRecord:
    source: str                 # "fec", "congress", ...
    cite_url: str               # public page a voter can open (never an API URL with a key)
    fetched_at: str             # ISO timestamp, UTC
    data: object                # parsed result
    fingerprint: str = field(default="")

    def __post_init__(self):
        if not self.fingerprint:
            blob = json.dumps(self.data, sort_keys=True, default=str)
            self.fingerprint = hashlib.sha256(blob.encode()).hexdigest()[:16]


def check_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme != "https" or (u.hostname or "") not in ALLOWED_HOSTS:
        raise BlockedURL(f"Blocked URL (not an allowlisted HTTPS source): {u.scheme}://{u.hostname}")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SourceClient:
    """httpx wrapper used by every adapter. Pass `transport` in tests to replay fixtures."""

    def __init__(self, *, headers: dict | None = None, timeout: float | None = None,
                 transport: httpx.BaseTransport | None = None, retries: int = 1):
        self._secrets = [v for v in (headers or {}).values() if v]
        self.retries = retries
        self.client = httpx.Client(
            timeout=timeout or config.HTTP_TIMEOUT_S,
            headers={"User-Agent": config.USER_AGENT, **(headers or {})},
            transport=transport,
            follow_redirects=False,
        )

    def _scrub(self, text: str) -> str:
        for s in self._secrets:
            text = text.replace(s, "***")
        return text

    def get_json(self, url: str, params: dict | None = None) -> dict:
        check_url(url)
        last = ""
        for attempt in range(self.retries + 1):
            try:
                r = self.client.get(url, params={k: v for k, v in (params or {}).items() if v is not None})
            except httpx.HTTPError as e:
                last = f"{type(e).__name__}"
            else:
                if r.status_code == 200:
                    return r.json()
                last = f"HTTP {r.status_code}: {self._scrub(r.text[:200])}"
                if r.status_code not in (429, 500, 502, 503, 504):
                    break
            if attempt < self.retries:
                time.sleep(1.5 * (attempt + 1))
        host = urlparse(url).hostname
        raise SourceError(f"{host} failed ({last})")

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
