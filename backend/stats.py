"""Anonymous usage totals: counts only, never addresses, IPs, cookies or anything per person.

What is counted (each is just a number that goes up by one):
    lookup:all, lookup:<STATE>, lookup:zip_only     a ballot lookup succeeded (state only)
    card:<CARD_ID>, lang:<en|es|zh>                  a card was opened, and in which language
    share:<whatsapp|wechat|more|copy>                a share button was used
    visit                                            the home page was loaded (not unique visitors)

Storage: an Upstash Redis database if UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN are set
(free tier; survives restarts), otherwise memory (resets whenever the server restarts).
Totals are kept overall and per day (daily buckets expire after 120 days). Failures never affect
the voter: counting is best-effort and runs off the request path.
"""

from __future__ import annotations

import os
import re
import threading
from collections import defaultdict
from datetime import date, timedelta

import httpx

def _env(name: str) -> str:
    # tolerate the usual copy-paste slips: spaces, newlines, surrounding quotes
    return os.getenv(name, "").strip().strip('"').strip("'").strip()


URL = _env("UPSTASH_REDIS_REST_URL").rstrip("/")
TOKEN = _env("UPSTASH_REDIS_REST_TOKEN")
DAY_TTL = 120 * 24 * 3600
FIELD = re.compile(r"^[a-z_]+:[A-Za-z0-9_-]{1,60}$|^visit$")

_mem: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
_lock = threading.Lock()


def backend() -> str:
    return "upstash" if URL and TOKEN else "memory"


def _today() -> str:
    return date.today().isoformat()


def count(*fields: str) -> None:
    """Add one to each field (overall and today). Silently ignores anything that isn't a plain label."""
    fields = tuple(f for f in fields if FIELD.match(f))
    if not fields:
        return
    day = f"d:{_today()}"
    if backend() == "memory":
        with _lock:
            for f in fields:
                _mem["total"][f] += 1
                _mem[day][f] += 1
        return
    cmds = [cmd for f in fields for cmd in (["HINCRBY", "total", f, 1], ["HINCRBY", day, f, 1])]
    cmds.append(["EXPIRE", day, DAY_TTL])
    threading.Thread(target=_send, args=(cmds,), daemon=True).start()


def _send(cmds: list) -> None:
    try:
        httpx.post(f"{URL}/pipeline", json=cmds, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=5)
    except Exception:
        pass   # counting must never break the app


def _hgetall_many(keys: list[str]) -> list[dict[str, int]]:
    if backend() == "memory":
        with _lock:
            return [dict(_mem.get(k, {})) for k in keys]
    r = httpx.post(f"{URL}/pipeline", json=[["HGETALL", k] for k in keys],
                   headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
    if r.status_code != 200 or not isinstance(body, list):
        msg = body.get("error") if isinstance(body, dict) else r.text[:120]
        raise StatsUnavailable(f"Upstash returned HTTP {r.status_code}: {str(msg).replace(TOKEN, '***')}")
    out = []
    for item in body:
        flat = item.get("result") or []
        out.append({flat[i]: int(flat[i + 1]) for i in range(0, len(flat), 2)})
    return out


class StatsUnavailable(RuntimeError):
    pass


def report(days: int = 14) -> dict:
    """Totals overall and per day, grouped for reading. Never raises: shows the problem instead."""
    day_keys = [f"d:{(date.today() - timedelta(days=i)).isoformat()}" for i in range(days)]
    try:
        total, *per_day = _hgetall_many(["total", *day_keys])
    except Exception as e:
        return {"storage": backend(), "error": f"Totals unavailable right now ({str(e)[:200]})",
                "note": "Anonymous totals only: no addresses, IPs, cookies or per-person data.",
                "total": {}, "by_day": {}}

    def group(d: dict[str, int]) -> dict:
        g: dict = defaultdict(dict)
        for k, v in d.items():
            kind, _, name = k.partition(":")
            if name:
                g[kind][name] = v
            else:
                g[kind] = v
        return {k: (dict(sorted(v.items(), key=lambda kv: -kv[1])) if isinstance(v, dict) else v) for k, v in g.items()}

    return {
        "storage": backend(),
        "note": "Anonymous totals only: no addresses, IPs, cookies or per-person data.",
        "total": group(total),
        "by_day": {k[2:]: group(v) for k, v in zip(day_keys, per_day) if v},
    }
