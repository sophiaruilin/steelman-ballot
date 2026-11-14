"""Offline tests for the FEC and Congress.gov adapters and the locked-down HTTP client.

Responses were recorded once from the live APIs (backend/sources/replay.py) and are replayed
here, so these tests need no network and no API keys.
"""

from datetime import date
from pathlib import Path

import httpx
import pytest

from backend.sources.congress import Congress, bill_url, current_congress
from backend.sources.fec import FEC
from backend.sources.http import BlockedURL, SourceClient, SourceError, check_url
from backend.sources.replay import ReplayTransport

FIX = Path(__file__).parent / "fixtures"


# ---- FEC ("Funded by") -------------------------------------------------------

@pytest.fixture
def fec():
    with FEC(transport=ReplayTransport(FIX / "fec_ga_senate.json")) as f:
        yield f


def test_fec_candidates_ga_senate(fec):
    rec = fec.candidates("GA", "S", cycle=2026)
    names = [c["name"] for c in rec.data["candidates"]]
    assert "OSSOFF, T. JONATHAN" in names
    assert rec.cite_url == "https://www.fec.gov/data/elections/senate/GA/2026/"
    assert rec.source == "fec" and rec.fingerprint


def test_fec_duplicate_filings_shown_once(fec):
    rec = fec.candidates("TX", "H", district=10, cycle=2026)
    names = [c["name"] for c in rec.data["candidates"]]
    assert names.count("BROWN, ROBERT") == 1 and names.count("ECKHARDT, SARAH") == 1
    brown = next(c for c in rec.data["candidates"] if c["name"] == "BROWN, ROBERT")
    assert brown["candidate_id"] == "H6TX17127" and brown["other_ids"] == ["H6TX17135"]


def test_fec_money_breakdown(fec):
    m = fec.money("S8GA00180", state="GA", cycle=2026).data
    assert m["raised"] > 100_000_000
    assert 0 < m["small_donor_share"] < 1 and 0 < m["in_state_share"] < 1
    assert m["from_pacs_share"] < 0.05
    assert set(m["donations_by_size"]) == {"$200 and under", "$200.01-$499", "$500-$999", "$1,000-$1,999", "$2,000+"}
    assert len(m["top_pacs"]) == 5


def test_fec_money_cites_public_page_not_api(fec):
    rec = fec.money("S8GA00180", state="GA", cycle=2026)
    assert rec.cite_url.startswith("https://www.fec.gov/data/candidate/S8GA00180")
    assert "api_key" not in rec.cite_url


# ---- Congress.gov ("Did") ----------------------------------------------------

@pytest.fixture
def cg():
    with Congress(transport=ReplayTransport(FIX / "congress_tx10.json")) as c:
        yield c


def test_congress_members_tx10(cg):
    rec = cg.members("TX", district=10, congress=119)
    assert [m["name"] for m in rec.data["house"]] == ["McCaul, Michael T."]
    assert len(rec.data["senate"]) == 2
    assert rec.data["house"][0]["cite_url"].startswith("https://bioguide.congress.gov/")


def test_congress_bills_sorted_and_cited(cg):
    rec = cg.bills("M001157", kind="sponsored")
    bills = rec.data["bills"]
    assert bills and all(b["title"] for b in bills)
    dates = [b["introduced"] for b in bills]
    assert dates == sorted(dates, reverse=True)
    assert all(b["cite_url"].startswith("https://www.congress.gov/bill/") for b in bills)


def test_current_congress():
    assert current_congress(date(2026, 11, 13)) == 119
    assert current_congress(date(2027, 1, 2)) == 119
    assert current_congress(date(2027, 1, 3)) == 120


def test_bill_url():
    assert bill_url(119, "HR", "8697") == "https://www.congress.gov/bill/119th-congress/house-bill/8697"


# ---- Security: allowlist and key handling ------------------------------------

@pytest.mark.parametrize("url", [
    "http://api.open.fec.gov/v1/candidates/",          # not HTTPS
    "https://texas-sos-elections.com/ballot",          # look-alike, not allowlisted
    "https://169.254.169.254/latest/meta-data/",       # cloud metadata (SSRF)
    "https://localhost:8000/admin",                    # our own server
    "https://api.open.fec.gov.evil.com/v1/",           # allowlisted name as a prefix
])
def test_blocked_urls(url):
    with pytest.raises(BlockedURL):
        check_url(url)


def test_allowed_url_passes():
    check_url("https://api.open.fec.gov/v1/candidates/")


def test_error_message_never_contains_key():
    secret = "SECRET-KEY-1234567890"

    def echo(request):  # a server that echoes the key back in its error text
        return httpx.Response(403, text=f"bad key {request.headers.get('X-Api-Key')}")

    c = SourceClient(headers={"X-Api-Key": secret}, transport=httpx.MockTransport(echo), retries=0)
    with pytest.raises(SourceError) as e:
        c.get_json("https://api.open.fec.gov/v1/candidates/")
    assert secret not in str(e.value) and "***" in str(e.value)


def test_key_sent_in_header_not_url():
    seen = {}

    def capture(request):
        seen["url"], seen["hdr"] = str(request.url), request.headers.get("X-Api-Key")
        return httpx.Response(200, json={})

    SourceClient(headers={"X-Api-Key": "k123"}, transport=httpx.MockTransport(capture)).get_json(
        "https://api.congress.gov/v3/member", {"format": "json"})
    assert "k123" not in seen["url"] and seen["hdr"] == "k123"
