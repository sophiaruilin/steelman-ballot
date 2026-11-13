"""Address -> election districts, using the free U.S. Census Geocoder (no API key).

    from backend.sources.geocoder import geocode
    j = geocode("165 Whitney Ave, New Haven, CT 06511")
    j.state_abbr, j.congressional_district, j.jurisdiction_key

The jurisdiction_key is the cache key: two addresses with the same key see the same
federal, state-legislative, county and city contests, so they share one research run.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import httpx

from backend import config

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"

# State FIPS -> postal abbreviation (50 states + DC)
STATE_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY",
}


class AddressNotFound(ValueError):
    """The Census Geocoder could not match the address."""


@dataclass(frozen=True)
class Area:
    name: str
    geoid: str


@dataclass(frozen=True)
class Jurisdiction:
    matched_address: str
    state_name: str
    state_abbr: str
    state_fips: str
    county: Area | None                 # in CT these are "Planning Regions"
    county_subdivision: Area | None     # town / township (where local races often live)
    place: Area | None                  # incorporated city, if any
    congressional_district: Area | None
    state_senate: Area | None           # NE is unicameral: senate only
    state_house: Area | None
    school_district: Area | None
    congress_label: str                 # e.g. "120th Congressional Districts"

    @property
    def jurisdiction_key(self) -> str:
        parts = [self.state_abbr]
        for tag, area in (
            ("cd", self.congressional_district), ("sldu", self.state_senate),
            ("sldl", self.state_house), ("county", self.county),
            ("cousub", self.county_subdivision), ("place", self.place),
        ):
            if area:
                parts.append(f"{tag}-{area.geoid}")
        return "|".join(parts)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["jurisdiction_key"] = self.jurisdiction_key
        return d


def _first(geos: dict, *, exact: str | None = None, pattern: str | None = None) -> tuple[Area | None, str]:
    for key, items in geos.items():
        hit = key == exact if exact else bool(re.search(pattern, key))
        if hit and items:
            x = items[0]
            return Area(name=x.get("NAME", ""), geoid=x.get("GEOID", "")), key
    return None, ""


def parse(payload: dict) -> Jurisdiction:
    """Turn a Census Geocoder JSON response into a Jurisdiction (pure, testable offline)."""
    matches = payload.get("result", {}).get("addressMatches", [])
    if not matches:
        raise AddressNotFound("No match for that address. Check the street, city, state and ZIP.")
    m = matches[0]
    geos = m.get("geographies", {})
    state, _ = _first(geos, exact="States")
    if not state:
        raise AddressNotFound("Address matched but no state was returned.")
    cd, cd_label = _first(geos, pattern=r"Congressional Districts$")
    return Jurisdiction(
        matched_address=m.get("matchedAddress", ""),
        state_name=state.name,
        state_abbr=STATE_FIPS.get(state.geoid, state.geoid),
        state_fips=state.geoid,
        county=_first(geos, exact="Counties")[0],
        county_subdivision=_first(geos, exact="County Subdivisions")[0],
        place=_first(geos, exact="Incorporated Places")[0],
        congressional_district=cd,
        state_senate=_first(geos, pattern=r"State Legislative Districts - Upper$")[0],
        state_house=_first(geos, pattern=r"State Legislative Districts - Lower$")[0],
        school_district=_first(geos, pattern=r"School Districts$")[0],
        congress_label=cd_label,
    )


def geocode(address: str, *, client: httpx.Client | None = None) -> Jurisdiction:
    """Look up an address with the Census Geocoder and return its election districts."""
    address = (address or "").strip()
    if len(address) < 5 or len(address) > 200:
        raise AddressNotFound("Enter a full street address (5-200 characters).")
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "all",
        "format": "json",
    }
    own = client is None
    client = client or httpx.Client(timeout=config.HTTP_TIMEOUT_S, headers={"User-Agent": config.USER_AGENT})
    try:
        r = client.get(CENSUS_URL, params=params)
        r.raise_for_status()
        return parse(r.json())
    finally:
        if own:
            client.close()
