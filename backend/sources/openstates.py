"""Open States adapter: state legislators for an address, and the bills they authored ("Did").

    with OpenStates() as os_:
        people = os_.legislators(lat=30.2747, lng=-97.7404)        # state house + senate members
        bills = os_.bills(people.data["legislators"][0])          # their recent bills

Matching bills to a legislator: Open States links most sponsorships to a person ID, but some
are stored only as a last name ("Hinojosa"), and a state can have several legislators with
that name. A bill counts as theirs if the sponsorship is linked to their ID ("linked"), or if
it's unlinked, the last name matches, and the bill started in their chamber ("name_match").
The Critic treats "name_match" as one-source-only evidence.
"""

from __future__ import annotations

import re
import time

import httpx

from backend import config
from backend.sources.filters import is_ceremonial
from backend.sources.http import SourceClient, SourceError, SourceRecord, now_iso

BASE = "https://v3.openstates.org"
MIN_INTERVAL_S = 1.0   # be gentle with the free tier


def _norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", (name or "").split(",")[0].lower())


def _legislator(x: dict) -> dict:
    role = x.get("current_role") or {}
    return {
        "id": x["id"],
        "name": x.get("name"),
        "family_name": x.get("family_name"),
        "party": x.get("party"),
        "chamber": role.get("org_classification"),      # "upper" / "lower"
        "title": role.get("title"),
        "district": role.get("district"),
        "state": (x.get("jurisdiction") or {}).get("name"),
        "photo": x.get("image"),
        "email": x.get("email"),
        "cite_url": x.get("openstates_url"),
    }


class OpenStates:
    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        if not config.OPENSTATES_API_KEY and transport is None:
            raise SourceError("OPENSTATES_API_KEY is not set (see .env.example).")
        self.http = SourceClient(headers={"X-API-KEY": config.OPENSTATES_API_KEY}, transport=transport)
        self._live = transport is None
        self._last = 0.0

    def _get(self, path: str, params: dict) -> dict:
        if self._live:
            wait = MIN_INTERVAL_S - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
        return self.http.get_json(f"{BASE}{path}", params)

    def legislators(self, *, lat: float, lng: float) -> SourceRecord:
        """Current STATE legislators whose districts contain this point (federal members dropped)."""
        d = self._get("/people.geo", {"lat": round(lat, 5), "lng": round(lng, 5)})
        people = [
            _legislator(x) for x in d.get("results", [])
            if (x.get("jurisdiction") or {}).get("classification") == "state"
        ]
        people.sort(key=lambda p: (p["chamber"] != "upper", p["name"] or ""))
        state = people[0]["state"] if people else None
        cite = people[0]["cite_url"] if people else "https://openstates.org/"
        return SourceRecord("openstates", cite, now_iso(), {"state": state, "legislators": people})

    def bills(self, person: dict, *, limit: int = 10, scan: int = 40) -> SourceRecord:
        """Most recent bills this legislator authored (primary sponsor)."""
        d = self._get("/bills", {
            "jurisdiction": person["state"], "sponsor": person["family_name"],
            "sort": "latest_action_desc", "include": "sponsorships", "per_page": min(scan, 20),
        })
        fam, chamber = _norm(person["family_name"]), person["chamber"]
        rows, ceremonial = [], 0
        for b in d.get("results", []):
            match = None
            for s in b.get("sponsorships", []):
                if not s.get("primary"):
                    continue
                linked = (s.get("person") or {}).get("id")
                if linked == person["id"]:
                    match = "linked"
                    break
                if linked is None and _norm(s.get("name")) == fam and \
                        (b.get("from_organization") or {}).get("classification") == chamber:
                    match = "name_match"
            if not match:
                continue
            if is_ceremonial(b.get("title")):
                ceremonial += 1
                continue
            rows.append({
                "bill": b.get("identifier"),
                "session": b.get("session"),
                "title": b.get("title"),
                "subjects": b.get("subject") or [],
                "latest_action": b.get("latest_action_description"),
                "latest_action_date": b.get("latest_action_date"),
                "match": match,
                "cite_url": b.get("openstates_url"),
            })
            if len(rows) >= limit:
                break
        return SourceRecord("openstates", person.get("cite_url") or "https://openstates.org/", now_iso(),
                            {"person_id": person["id"], "name": person["name"], "bills": rows,
                             "ceremonial_skipped": ceremonial})

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
