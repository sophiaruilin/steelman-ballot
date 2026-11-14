"""Ballot Mapper: address -> the contests on that voter's ballot, from official sources first.

    python -m backend.agents.ballot_mapper "1315 10th St, Sacramento, CA 95814"

Statewide measures come from each state's official voter guide (parser per state below).
Federal races come from the Census districts + FEC filings. State legislative races list the
current officeholders from Open States; the official county sample ballot settles who is
actually on the ballot (it always wins when sources disagree).

States without an official-guide parser yet return `measures_status="not_mapped"` so the
dashboard shows a coverage badge instead of silently missing measures.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field

from backend.sources.geocoder import Jurisdiction, geocode
from backend.sources.web import WebReader

MEASURE_TYPES = (r"Legislative Statute|Legislative Constitutional Amendment|"
                 r"Initiative Constitutional Amendment(?: and Statute)?|Initiative Statute|Referendum[^\n.]*")


@dataclass
class Measure:
    number: str
    official_title: str
    measure_type: str
    urls: list[str]
    source_url: str


@dataclass
class Race:
    office: str            # "U.S. Senate", "U.S. House CA-7", "State Senate District 8", ...
    level: str             # "federal" / "state_legislative"
    district: str | None
    lookup: dict           # how the profiler finds candidates (FEC ids, Open States ids...)
    confirmed: bool = True # False = may not be on this ballot; check the official sample ballot


@dataclass
class Ballot:
    election: str
    jurisdiction_key: str
    state: str
    districts: dict
    measures: list[Measure] = field(default_factory=list)
    races: list[Race] = field(default_factory=list)
    measures_status: str = "not_mapped"     # "official" / "not_mapped"
    official_ballot_note: str = ("Confirm against your county's official sample ballot. "
                                 "If anything here disagrees with it, the official ballot is right.")


# ---- Official-guide parsers, one per state ---------------------------------------

def parse_ca_guide(text: str) -> list[tuple[str, str, str]]:
    """(number, title, type) from the visible text of voterguide.sos.ca.gov/propositions/."""
    out = []
    for m in re.finditer(rf"(?m)^\s*(\d{{1,2}})\s+([A-Z][^\n]{{8,220}}?)\.\s*({MEASURE_TYPES})\.", text):
        out.append((m.group(1), m.group(2).strip(), m.group(3).strip()))
    return out


def ca_measures(reader: WebReader, election: str) -> list[Measure]:
    if election != "2026-11-03":
        return []  # the CA guide site shows only the current election
    url = "https://voterguide.sos.ca.gov/propositions/"
    text = reader.fetch(url).data["text"]
    base = "https://voterguide.sos.ca.gov/propositions/{n}/"
    return [
        Measure(number=f"Prop {n}", official_title=title, measure_type=kind, source_url=url,
                urls=[base.format(n=n) + p for p in ("title-summary.htm", "analysis.htm", "arguments-rebuttals.htm")])
        for n, title, kind in parse_ca_guide(text)
    ]


STATE_GUIDES = {"CA": ca_measures}


# ---- Races from districts --------------------------------------------------------

def races_for(j: Jurisdiction, election: str) -> list[Race]:
    year = int(election[:4])
    races = []
    if j.congressional_district:
        n = j.congressional_district.geoid[-2:]
        races.append(Race(office=f"U.S. House {j.state_abbr}-{int(n)}", level="federal", district=n,
                          lookup={"fec": {"state": j.state_abbr, "office": "H", "district": int(n), "cycle": year}}))
    # Senate: whether a seat is up is settled by FEC filings for this cycle (checked by the profiler).
    races.append(Race(office="U.S. Senate", level="federal", district=None, confirmed=False,
                      lookup={"fec": {"state": j.state_abbr, "office": "S", "cycle": year}}))
    if j.state_senate:
        races.append(Race(office=j.state_senate.name, level="state_legislative", district=j.state_senate.geoid,
                          lookup={"openstates": {"lat": j.lat, "lng": j.lng, "chamber": "upper"}}))
    if j.state_house:
        races.append(Race(office=j.state_house.name, level="state_legislative", district=j.state_house.geoid,
                          lookup={"openstates": {"lat": j.lat, "lng": j.lng, "chamber": "lower"}}))
    return races


def map_ballot(address: str, election: str = "2026-11-03", reader: WebReader | None = None,
               jurisdiction: Jurisdiction | None = None) -> Ballot:
    j = jurisdiction or geocode(address)
    reader = reader or WebReader()
    b = Ballot(election=election, jurisdiction_key=j.jurisdiction_key, state=j.state_abbr,
               districts={k: (v.name if hasattr(v, "name") else v) for k, v in {
                   "congressional": j.congressional_district, "state_senate": j.state_senate,
                   "state_house": j.state_house, "county": j.county, "city": j.place}.items() if v})
    guide = STATE_GUIDES.get(j.state_abbr)
    if guide:
        b.measures = guide(reader, election)
        b.measures_status = "official" if b.measures else "not_mapped"
    b.races = races_for(j, election)
    return b


if __name__ == "__main__":
    addr = sys.argv[1] if len(sys.argv) > 1 else "1315 10th St, Sacramento, CA 95814"
    print(json.dumps(asdict(map_ballot(addr)), indent=2, ensure_ascii=False))
