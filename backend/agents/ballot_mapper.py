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
    number: str                 # as voters see it: "Prop 3", "Question 4", "Proposal 2"
    official_title: str
    measure_type: str
    urls: list[str]             # official pages the Measure Analyst starts from
    source_url: str
    slug: str = ""              # card id part: "prop-3", "question-4", "nyc-proposal-2"
    label: str = ""             # for the agent: "California Proposition 3"
    scope: str = "statewide"    # "statewide" or a local area, e.g. "New York City"


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
                urls=[base.format(n=n) + p for p in ("title-summary.htm", "analysis.htm", "arguments-rebuttals.htm")],
                slug=f"prop-{n}", label=f"California Proposition {n}")
        for n, title, kind in parse_ca_guide(text)
    ]


# Massachusetts: the official "Information for Voters" guide. Its web pages sit behind bot
# protection (respected), but the official PDF is public and allowed by robots.txt.
MA_PDF = ("https://www.sec.state.ma.us/divisions/elections/download/information-for-voters/archive/"
          "IFV_2026%20English.pdf")


def parse_ma_guide(pages: list[str]) -> list[tuple[str, str, int, int]]:
    """(number, title, first_page, last_page) of each question's summary-and-arguments section."""
    toc = "\n".join(pages[:5])
    titles = {m.group(1): m.group(2).strip(" .")
              for m in re.finditer(r"Question (\d+) - ([^\n.]+?)\s*\.{3,}", toc)}
    starts = {}
    for i, text in enumerate(pages, start=1):
        for m in re.finditer(r"QUESTION (\d+): (?:Law Proposed|Referendum|Proposed Amendment)", text):
            starts.setdefault(m.group(1), i)
    nums = sorted(starts, key=int)
    out = []
    for k, n in enumerate(nums):
        first = starts[n]
        last = (starts[nums[k + 1]] - 1) if k + 1 < len(nums) else first + 1
        out.append((n, titles.get(n, f"Question {n}"), first, max(first, min(last, first + 2))))
    return out


def ma_measures(reader: WebReader, election: str) -> list[Measure]:
    if election != "2026-11-03":
        return []
    pages = reader._pdf_pages(MA_PDF)
    return [
        Measure(number=f"Question {n}", official_title=title, measure_type="Statewide ballot question",
                source_url=f"{MA_PDF}#page=3",
                urls=[f"{MA_PDF}#page={a}&pages={a}-{b}"], slug=f"question-{n}",
                label=f"Massachusetts Question {n}")
        for n, title, a, b in parse_ma_guide(pages)
    ]


# New York: no statewide proposals on the Nov 3, 2026 ballot. New York City voters have five City
# Charter proposals; NYC Votes (the city's Campaign Finance Board) publishes summaries of public
# statements for and against each one.
NYC_PLACE_GEOID = "3651000"
NYC_GUIDE = "https://www.nycvotes.org/whats-on-the-ballot/2026-general-election-voter-guide/ballot-proposals-2026/"


def parse_nyc_guide(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2).strip())
            for m in re.finditer(r"(?m)^\s*(\d)\. ([A-Z][^\n]{8,200})$", text)]


def nyc_measures(reader: WebReader, election: str) -> list[Measure]:
    if election != "2026-11-03":
        return []
    text = reader.fetch(NYC_GUIDE).data["text"]
    return [
        Measure(number=f"Proposal {n}", official_title=title, measure_type="New York City Charter amendment",
                source_url=NYC_GUIDE, urls=[f"{NYC_GUIDE}ballot-proposal-{n}/"], slug=f"nyc-proposal-{n}",
                label=f"New York City Ballot Proposal {n}", scope="New York City")
        for n, title in parse_nyc_guide(text)
    ]


def ny_measures(reader: WebReader, election: str, place_geoid: str | None = None) -> list[Measure]:
    return nyc_measures(reader, election) if place_geoid == NYC_PLACE_GEOID else []


STATE_GUIDES = {"CA": ca_measures, "MA": ma_measures}
def ct_measures(reader: WebReader, election: str, place_geoid: str | None = None) -> list[Measure]:
    # Connecticut has no statewide ballot questions on Nov 3, 2026 (Secretary of the State's 2026
    # election guide, as reported by Decode the Vote). Town charter questions vary by municipality
    # and are published by each town clerk; not covered yet.
    return []


LOCAL_GUIDES = {"NY": ny_measures, "CT": ct_measures}   # need the voter's city/town to know what's on the ballot
COVERED_STATES = {
    "CA": "Statewide propositions and statewide offices",
    "MA": "Statewide ballot questions",
    "NY": "New York City proposals (no statewide proposals in 2026)",
    "CT": "No statewide questions in 2026; races shown (town charter questions not covered yet)",
}
# How each covered state shows on the map: full = statewide measures, part = local measures only,
# checked = we confirmed there are no statewide measures this election.
MAP_KIND = {"CA": "full", "MA": "full", "NY": "part", "CT": "checked"}


def measures_for(j: Jurisdiction, election: str, reader: WebReader) -> tuple[list[Measure], str]:
    """Measures on this voter's ballot and a coverage status: official / none_on_ballot / not_mapped."""
    if j.state_abbr in STATE_GUIDES:
        ms = STATE_GUIDES[j.state_abbr](reader, election)
        return ms, ("official" if ms else "not_mapped")
    if j.state_abbr in LOCAL_GUIDES:
        ms = LOCAL_GUIDES[j.state_abbr](reader, election, j.place.geoid if j.place else None)
        return ms, "official" if ms else "none_on_ballot"
    return [], "not_mapped"


# ---- Races from districts --------------------------------------------------------

# States with a U.S. Senate seat on the ballot: the 33 Class II seats in 2026, plus the 2026 special
# elections in Florida and Ohio. (California, New York and Connecticut have no Senate race in 2026.)
SENATE_UP = {
    2026: {"AL", "AK", "AR", "CO", "DE", "GA", "ID", "IL", "IA", "KS", "KY", "LA", "ME", "MA", "MI", "MN",
           "MS", "MT", "NE", "NH", "NJ", "NM", "NC", "OK", "OR", "RI", "SC", "SD", "TN", "TX", "VA", "WV",
           "WY", "FL", "OH"},
}


def races_for(j: Jurisdiction, election: str) -> list[Race]:
    year = int(election[:4])
    races = []
    if j.congressional_district:
        n = j.congressional_district.geoid[-2:]
        races.append(Race(office=f"U.S. House {j.state_abbr}-{int(n)}", level="federal", district=n,
                          lookup={"fec": {"state": j.state_abbr, "office": "H", "district": int(n), "cycle": year}}))
    # Senate: only list it where a seat is actually up. For years we have a schedule for, that is
    # settled; otherwise it stays unconfirmed (check the official sample ballot).
    if year in SENATE_UP:
        if j.state_abbr in SENATE_UP[year]:
            races.append(Race(office="U.S. Senate", level="federal", district=None,
                              lookup={"fec": {"state": j.state_abbr, "office": "S", "cycle": year}}))
    else:
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
    b.measures, b.measures_status = measures_for(j, election, reader)
    b.races = races_for(j, election)
    return b


if __name__ == "__main__":
    addr = sys.argv[1] if len(sys.argv) > 1 else "1315 10th St, Sacramento, CA 95814"
    print(json.dumps(asdict(map_ballot(addr)), indent=2, ensure_ascii=False))
