"""Congress.gov adapter: who represents an address in Congress, and what they've done ("Did").

    with Congress() as cg:
        reps = cg.members("TX", district=10)          # House member + both senators
        bills = cg.bills("M001157", kind="sponsored")  # recent bills they sponsored

Citations point to public congress.gov / bioguide pages, never to API URLs.
"""

from __future__ import annotations

from datetime import date

import httpx

from backend import config
from backend.sources.http import SourceClient, SourceError, SourceRecord, now_iso

BASE = "https://api.congress.gov/v3"

BILL_SLUG = {
    "HR": "house-bill", "S": "senate-bill",
    "HRES": "house-resolution", "SRES": "senate-resolution",
    "HJRES": "house-joint-resolution", "SJRES": "senate-joint-resolution",
    "HCONRES": "house-concurrent-resolution", "SCONRES": "senate-concurrent-resolution",
}


def current_congress(today: date | None = None) -> int:
    """Congress number in session on a date (a new Congress starts Jan 3 of odd years)."""
    d = today or date.today()
    year = d.year - 1 if (d.year % 2 == 1 and (d.month, d.day) < (1, 3)) else d.year
    return (year - 1789) // 2 + 1


def bill_url(congress: int, bill_type: str, number: str) -> str:
    return f"https://www.congress.gov/bill/{congress}th-congress/{BILL_SLUG.get(bill_type.upper(), 'house-bill')}/{number}"


def member_url(bioguide_id: str) -> str:
    return f"https://bioguide.congress.gov/search/bio/{bioguide_id}"


def _member(x: dict) -> dict:
    terms = (x.get("terms") or {}).get("item") or []
    return {
        "bioguide_id": x["bioguideId"],
        "name": x.get("name"),
        "party": x.get("partyName"),
        "state": x.get("state"),
        "district": x.get("district"),
        "chamber": terms[-1].get("chamber") if terms else None,
        "serving_since": min((t.get("startYear") for t in terms if t.get("startYear")), default=None),
        "photo": (x.get("depiction") or {}).get("imageUrl"),
        "cite_url": member_url(x["bioguideId"]),
    }


class Congress:
    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        if not config.DATA_GOV_API_KEY and transport is None:
            raise SourceError("DATA_GOV_API_KEY is not set (see .env.example).")
        self.http = SourceClient(headers={"X-Api-Key": config.DATA_GOV_API_KEY}, transport=transport)

    def members(self, state: str, *, district: int | None = None, congress: int | None = None) -> SourceRecord:
        """Current House member for the district (if given) plus the state's two senators."""
        congress = congress or current_congress()
        q = {"format": "json", "currentMember": "true", "limit": 250}
        everyone = self.http.get_json(f"{BASE}/member/congress/{congress}/{state}", q).get("members", [])
        people = [_member(x) for x in everyone]
        senators = [m for m in people if m["chamber"] == "Senate"]
        house = [m for m in people if m["chamber"] == "House of Representatives"
                 and district is not None and int(m["district"] or 0) == int(district)]
        cite = f"https://www.congress.gov/members?q=%7B%22congress%22%3A{congress}%2C%22member-state%22%3A%22{state}%22%7D"
        return SourceRecord("congress", cite, now_iso(),
                            {"congress": congress, "state": state, "district": district,
                             "house": house, "senate": senators})

    def bills(self, bioguide_id: str, *, kind: str = "sponsored", limit: int = 10) -> SourceRecord:
        """Most recent bills a member sponsored or cosponsored (amendments are skipped)."""
        if kind not in ("sponsored", "cosponsored"):
            raise ValueError("kind must be 'sponsored' or 'cosponsored'")
        key = "sponsoredLegislation" if kind == "sponsored" else "cosponsoredLegislation"
        raw = self.http.get_json(f"{BASE}/member/{bioguide_id}/{kind}-legislation",
                                 {"format": "json", "limit": 50}).get(key, [])
        rows = []
        for b in raw:
            if not b.get("title") or not b.get("type") or not b.get("number"):
                continue  # amendments have no title/type
            la = b.get("latestAction") or {}
            rows.append({
                "congress": b.get("congress"),
                "bill": f"{b['type']} {b['number']}",
                "title": b["title"],
                "introduced": b.get("introducedDate"),
                "policy_area": (b.get("policyArea") or {}).get("name"),
                "latest_action": la.get("text"),
                "latest_action_date": la.get("actionDate"),
                "cite_url": bill_url(b["congress"], b["type"], b["number"]),
            })
        rows.sort(key=lambda r: r["introduced"] or "", reverse=True)
        rows = rows[:limit]
        return SourceRecord("congress", member_url(bioguide_id), now_iso(),
                            {"bioguide_id": bioguide_id, "kind": kind, "bills": rows})

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
