"""Offline tests for the geocoder parser and the cache policy (no network, no model calls)."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend import cache
from backend.sources.geocoder import AddressNotFound, parse

FIX = Path(__file__).parent / "fixtures"
UTC = timezone.utc


# ---- Geocoder --------------------------------------------------------------

def test_parse_new_haven_districts():
    j = parse(json.loads((FIX / "census_new_haven.json").read_text(encoding="utf-8")))
    assert j.state_abbr == "CT"
    assert j.congressional_district.name == "Congressional District 3"
    assert j.state_senate.name == "State Senate District 11"
    assert j.state_house.name == "State House District 96"
    assert j.place.name == "New Haven city"
    assert j.county_subdivision.name == "New Haven town"
    assert j.jurisdiction_key == (
        "CT|cd-0903|sldu-09011|sldl-09096|county-09170|cousub-0917052070|place-0952000"
    )


def test_parse_no_match_raises():
    with pytest.raises(AddressNotFound):
        parse({"result": {"addressMatches": []}})


# ---- Cache policy ----------------------------------------------------------

ELECTION = date(2027, 11, 2)


def entry(built: datetime, checked: datetime) -> cache.CacheEntry:
    return cache.CacheEntry("TX|cd-4810", "2027-11-02-general", built, checked)


def test_no_cache_means_full_refresh():
    assert cache.decide(None, now=datetime(2027, 10, 1, tzinfo=UTC), election_day=ELECTION) == "full_refresh"


def test_same_day_reuses_run_inside_60_days():
    now = datetime(2027, 10, 20, 15, 0, tzinfo=UTC)
    e = entry(built=now - timedelta(hours=5), checked=now - timedelta(minutes=20))
    assert cache.decide(e, now=now, election_day=ELECTION) == "serve"


def test_hourly_change_check_inside_60_days():
    now = datetime(2027, 10, 20, 15, 0, tzinfo=UTC)
    e = entry(built=now - timedelta(hours=5), checked=now - timedelta(hours=2))
    assert cache.decide(e, now=now, election_day=ELECTION) == "check"


def test_new_day_triggers_full_refresh_inside_60_days():
    now = datetime(2027, 10, 20, 0, 30, tzinfo=UTC)
    e = entry(built=now - timedelta(hours=1), checked=now - timedelta(hours=1))  # built yesterday
    assert cache.decide(e, now=now, election_day=ELECTION) == "full_refresh"


def test_far_from_election_is_weekly_with_daily_check():
    now = datetime(2027, 6, 1, 12, 0, tzinfo=UTC)
    assert cache.decide(entry(now - timedelta(days=3), now - timedelta(hours=3)),
                        now=now, election_day=ELECTION) == "serve"
    assert cache.decide(entry(now - timedelta(days=3), now - timedelta(hours=25)),
                        now=now, election_day=ELECTION) == "check"
    assert cache.decide(entry(now - timedelta(days=8), now - timedelta(hours=1)),
                        now=now, election_day=ELECTION) == "full_refresh"


def test_changed_sources_only_flags_what_moved():
    old = {"fec:C001": "a1", "ballot:tx": "b2"}
    new = {"fec:C001": "a9", "ballot:tx": "b2", "vote411:tx": "c3"}
    assert cache.changed_sources(old, new) == {"fec:C001", "vote411:tx"}


def test_save_and_load_roundtrip(tmp_path):
    now = datetime(2027, 10, 20, 15, 0, tzinfo=UTC)
    e = entry(now, now)
    e.payload = {"cards": [{"title": "Prop 1"}]}
    cache.save(e, cache_dir=tmp_path)
    back = cache.load(e.jurisdiction_key, e.election_id, cache_dir=tmp_path)
    assert back.payload == e.payload and back.built_at == now


# ---- Contest-level cache keys ----------------------------------------------------

def test_statewide_measure_shares_one_key_across_districts():
    # Two Californians in different districts get the SAME cached Prop 3 card.
    k1 = cache.contest_key("CA", "statewide", "prop-3")
    k2 = cache.contest_key("ca", "statewide", "prop-3")
    assert k1 == k2 == "CA|statewide|prop-3"
    assert cache.contest_key("TX", "cd-4810", "us-house") != cache.contest_key("TX", "cd-4807", "us-house")


def test_contest_cache_roundtrip_serves_same_day(tmp_path):
    now = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)
    key = cache.contest_key("CA", "statewide", "prop-3")
    cache.save(cache.CacheEntry(key, "2026-11-03", now, now, {"u": "fp"}, {"card": {"number": "Prop 3"}}),
               cache_dir=tmp_path)
    e = cache.load(key, "2026-11-03", cache_dir=tmp_path)
    assert cache.decide(e, now=now + timedelta(minutes=30), election_day=date(2026, 11, 3)) == "serve"
