"""Shared research cache: one run per jurisdiction + election, reused by every voter there.

Decision for each request (see decide()):
  * no cached run, or the full-refresh window has passed  -> "full_refresh" (run every agent)
  * change-check window has passed                        -> "check"  (ping sources, no LLM;
                                                              re-run only cards whose sources changed)
  * otherwise                                             -> "serve"  (instant, ~0 tokens)

The windows tighten as election day nears (config.REFRESH_POLICY):
  60+ days out: weekly full refresh, daily change check
  inside 60 days: daily full refresh, hourly change check
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from backend import config


def policy_for(days_to_election: int) -> tuple[int, int]:
    """(full refresh every N days, change check every N hours) for this distance to the election."""
    for threshold, full_days, check_hours in config.REFRESH_POLICY:
        if days_to_election >= threshold:
            return full_days, check_hours
    return config.REFRESH_POLICY[-1][1:]


@dataclass
class CacheEntry:
    jurisdiction_key: str
    election_id: str                 # e.g. "2026-11-03-general"
    built_at: datetime               # when the last full research run finished
    checked_at: datetime             # when sources were last pinged for changes
    fingerprints: dict[str, str] = field(default_factory=dict)   # source URL -> ETag / hash
    payload: dict = field(default_factory=dict)                  # the finished ballot cards

    def to_json(self) -> dict:
        return {
            "jurisdiction_key": self.jurisdiction_key,
            "election_id": self.election_id,
            "built_at": self.built_at.isoformat(),
            "checked_at": self.checked_at.isoformat(),
            "fingerprints": self.fingerprints,
            "payload": self.payload,
        }

    @classmethod
    def from_json(cls, d: dict) -> "CacheEntry":
        return cls(
            jurisdiction_key=d["jurisdiction_key"],
            election_id=d["election_id"],
            built_at=datetime.fromisoformat(d["built_at"]),
            checked_at=datetime.fromisoformat(d["checked_at"]),
            fingerprints=d.get("fingerprints", {}),
            payload=d.get("payload", {}),
        )


def decide(entry: CacheEntry | None, *, now: datetime, election_day: date) -> str:
    """Return "full_refresh", "check" or "serve" for this cached entry."""
    if entry is None:
        return "full_refresh"
    days_out = (election_day - now.date()).days
    full_days, check_hours = policy_for(days_out)
    # Inside 60 days "daily" means a new calendar day, not 24h since the last run.
    if full_days == 1:
        if entry.built_at.date() < now.date():
            return "full_refresh"
    elif now - entry.built_at >= timedelta(days=full_days):
        return "full_refresh"
    if now - entry.checked_at >= timedelta(hours=check_hours):
        return "check"
    return "serve"


def fingerprint_text(text: str) -> str:
    """Stable hash for a source page when it has no ETag / Last-Modified header."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()[:16]


def changed_sources(old: dict[str, str], new: dict[str, str]) -> set[str]:
    """Source URLs that are new or whose fingerprint changed since the cached run."""
    return {url for url, fp in new.items() if old.get(url) != fp}


# ---- Disk storage ---------------------------------------------------------

def _path(jurisdiction_key: str, election_id: str, cache_dir: Path | None = None) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{jurisdiction_key}__{election_id}")
    return (cache_dir or config.CACHE_DIR) / f"{safe}.json"


def load(jurisdiction_key: str, election_id: str, cache_dir: Path | None = None) -> CacheEntry | None:
    p = _path(jurisdiction_key, election_id, cache_dir)
    if not p.exists():
        return None
    try:
        return CacheEntry.from_json(json.loads(p.read_text(encoding="utf-8")))
    except (ValueError, KeyError):
        return None  # corrupt entry: treat as a miss and rebuild


def save(entry: CacheEntry, cache_dir: Path | None = None) -> Path:
    p = _path(entry.jurisdiction_key, entry.election_id, cache_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(entry.to_json(), indent=2), encoding="utf-8")
    tmp.replace(p)  # atomic: a reader never sees a half-written file
    return p


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---- Contest-level keys -------------------------------------------------------------
# Research is cached per CONTEST, not per voter's district combination: a statewide measure is
# the same card for every voter in the state, a House race the same for everyone in that district.
# A voter's ballot is then just a list of contest keys, assembled from the cache.

def contest_key(state: str, scope: str, contest_id: str) -> str:
    """e.g. contest_key("CA", "statewide", "prop-3") -> "CA|statewide|prop-3";
    contest_key("TX", "cd-4810", "us-house") -> "TX|cd-4810|us-house"."""
    return f"{state.upper()}|{scope}|{contest_id}"
