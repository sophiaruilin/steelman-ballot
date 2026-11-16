"""U.S. Senate appears only where a seat is actually on the 2026 ballot."""
from fastapi.testclient import TestClient

from backend.agents.ballot_mapper import SENATE_UP
from backend.app import app

client = TestClient(app)


def offices(zip_code):
    r = client.post("/api/ballot", json={"address": zip_code})
    assert r.status_code == 200
    return [x["office"] for x in r.json()["races"]]


def test_no_senate_race_in_california_2026():
    assert "U.S. Senate" not in offices("95814")


def test_senate_race_listed_in_massachusetts_2026():
    assert "U.S. Senate" in offices("02139")


def test_schedule_covers_class_ii_plus_specials():
    up = SENATE_UP[2026]
    assert len(up) == 35 and {"FL", "OH", "MA", "TX"} <= up
    assert not ({"CA", "NY", "CT"} & up)
