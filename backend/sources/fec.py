"""OpenFEC adapter: federal candidates and who funds them ("Funded by").

    with FEC() as fec:
        cands = fec.candidates("GA", "S", cycle=2026)
        money = fec.money("S8GA00180", state="GA", cycle=2026)

Every method returns a SourceRecord whose cite_url is the candidate's public fec.gov page.
"""

from __future__ import annotations

from collections import defaultdict

import httpx

from backend import config
from backend.sources.http import SourceClient, SourceError, SourceRecord, now_iso

BASE = "https://api.open.fec.gov/v1"

# FEC "by_size" buckets (total given by one donor in the cycle)
SIZE_LABELS = {0: "$200 and under", 200: "$200.01-$499", 500: "$500-$999", 1000: "$1,000-$1,999", 2000: "$2,000+"}


def cite_candidate(candidate_id: str, cycle: int) -> str:
    return f"https://www.fec.gov/data/candidate/{candidate_id}/?cycle={cycle}"


def _share(part: float | None, whole: float | None) -> float | None:
    return round(part / whole, 3) if part is not None and whole else None


class FEC:
    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        if not config.DATA_GOV_API_KEY and transport is None:
            raise SourceError("DATA_GOV_API_KEY is not set (see .env.example).")
        self.http = SourceClient(headers={"X-Api-Key": config.DATA_GOV_API_KEY}, transport=transport)

    # ---- candidates ----------------------------------------------------------
    def candidates(self, state: str, office: str, *, district: int | None = None, cycle: int) -> SourceRecord:
        """Filed candidates for one federal race. office: "H" (House), "S" (Senate) or "P"."""
        params = {"state": state, "office": office, "election_year": cycle, "candidate_status": "C",
                  "per_page": 100, "sort": "name"}
        if office == "H" and district is not None:
            params["district"] = f"{int(district):02d}"
        d = self.http.get_json(f"{BASE}/candidates/", params)
        # FEC sometimes has two IDs for one person (duplicate filings). Keep the most recently
        # active ID and list the others, so the card shows each person once.
        by_name: dict[str, dict] = {}
        for x in d.get("results", []):
            row = {
                "candidate_id": x["candidate_id"],
                "name": x["name"],
                "party": x.get("party_full") or x.get("party"),
                "status": x.get("incumbent_challenge_full"),
                "office": x.get("office_full"),
                "district": x.get("district"),
                "has_raised_funds": x.get("has_raised_funds"),
                "last_file_date": x.get("last_file_date"),
                "other_ids": [],
            }
            prev = by_name.get(row["name"])
            if prev is None:
                by_name[row["name"]] = row
                continue
            keep, drop = (row, prev) if (row["last_file_date"] or "") > (prev["last_file_date"] or "") else (prev, row)
            keep["other_ids"] = prev["other_ids"] + row["other_ids"] + [drop["candidate_id"]]
            by_name[row["name"]] = keep
        rows = list(by_name.values())
        race = f"{state} {'Senate' if office == 'S' else 'House district ' + str(district) if office == 'H' else 'President'}"
        cite = (f"https://www.fec.gov/data/elections/{'senate' if office == 'S' else 'house'}/{state}/"
                f"{'' if office == 'S' else f'{int(district or 0):02d}/'}{cycle}/")
        return SourceRecord("fec", cite, now_iso(), {"race": race, "cycle": cycle, "candidates": rows})

    # ---- money -----------------------------------------------------------------
    def money(self, candidate_id: str, *, state: str, cycle: int, top_n: int = 5) -> SourceRecord:
        """Totals, small-donor share, in-state share and top PAC contributors for one candidate."""
        p = {"cycle": cycle, "election_full": "true"}
        totals = (self.http.get_json(f"{BASE}/candidate/{candidate_id}/totals/", p).get("results") or [{}])[0]
        receipts = totals.get("receipts")
        indiv = (totals.get("individual_itemized_contributions") or 0) + (totals.get("individual_unitemized_contributions") or 0)

        by_size = self.http.get_json(f"{BASE}/schedules/schedule_a/by_size/by_candidate/",
                                     {**p, "candidate_id": candidate_id}).get("results", [])
        sizes = {SIZE_LABELS.get(x["size"], str(x["size"])): x["total"] for x in by_size}
        size_total = sum(x["total"] or 0 for x in by_size)

        by_state = self.http.get_json(f"{BASE}/schedules/schedule_a/by_state/by_candidate/",
                                      {**p, "candidate_id": candidate_id, "per_page": 100}).get("results", [])
        state_total = sum(x["total"] or 0 for x in by_state)
        in_state = sum(x["total"] or 0 for x in by_state if x.get("state") == state)

        top_pacs = self._top_pacs(candidate_id, cycle, top_n)

        data = {
            "candidate_id": candidate_id,
            "cycle": cycle,
            "coverage_end_date": (totals.get("coverage_end_date") or "")[:10] or None,
            "raised": receipts,
            "spent": totals.get("disbursements"),
            "cash_on_hand": totals.get("last_cash_on_hand_end_period"),
            "from_individuals_share": _share(indiv, receipts),
            "from_pacs": totals.get("other_political_committee_contributions"),
            "from_pacs_share": _share(totals.get("other_political_committee_contributions"), receipts),
            "small_donor_share": _share(sizes.get(SIZE_LABELS[0]), size_total),
            "in_state_share": _share(in_state, state_total),
            "donations_by_size": sizes,
            "top_pacs": top_pacs,
        }
        return SourceRecord("fec", cite_candidate(candidate_id, cycle), now_iso(), data)

    def _top_pacs(self, candidate_id: str, cycle: int, top_n: int) -> list[dict]:
        """Largest PAC contributors (FEC Form 3 line 11C) to the candidate's principal committee."""
        try:
            com = self.http.get_json(f"{BASE}/candidate/{candidate_id}/committees/",
                                     {"designation": "P", "cycle": cycle}).get("results", [])
            if not com:
                return []
            rows = self.http.get_json(f"{BASE}/schedules/schedule_a/", {
                "committee_id": com[0]["committee_id"], "two_year_transaction_period": cycle,
                "line_number": "F3-11C", "sort": "-contribution_receipt_amount", "per_page": 100,
            }).get("results", [])
        except SourceError:
            return []  # optional detail: the card still renders without it
        agg: dict[str, float] = defaultdict(float)
        for r in rows:
            agg[r.get("contributor_name") or "Unknown"] += r.get("contribution_receipt_amount") or 0
        top = sorted(agg.items(), key=lambda kv: -kv[1])[:top_n]
        return [{"name": n, "total": round(t, 2)} for n, t in top]

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
