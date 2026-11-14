"""Offline tests for the Critic's code checks and the Candidate Profiler's parsing/equal treatment."""

import json
from pathlib import Path

from backend.agents import critic
from backend.agents.candidate_profiler import parse_ca_candidates
from backend.models import MeasureCard, RaceCard

FIX = Path(__file__).parent / "fixtures"
CARDS = Path(__file__).parent.parent / "output" / "cards"


def load_card(path):
    return MeasureCard(**json.loads(path.read_text(encoding="utf-8"))["card"])


# ---- Critic code checks (Safety demo: a sabotaged card fails automatically) -----------

def test_sabotaged_card_fails_code_checks():
    bad = load_card(FIX / "sabotaged_prop3_card.json")
    checks = critic.code_checks(bad)
    assert checks["recommendation"] == ["voters should vote"]
    assert {"common-sense", "devastating"} <= set(checks["loaded_words"])
    assert checks["words"]["ratio"] > 1.6
    fails = critic.hard_failures(checks)
    assert any("recommendation" in f for f in fails)
    assert any("unbalanced" in f.lower() for f in fails)
    assert any("same number of evidence" in f for f in fails)


def test_published_cards_pass_code_checks():
    for name in ("CA-2026-11-03-prop-1.json", "CA-2026-11-03-prop-3.json"):
        rec = json.loads((CARDS / name).read_text(encoding="utf-8"))
        assert rec["steelman_verified"] is True
        assert critic.hard_failures(critic.code_checks(MeasureCard(**rec["card"]))) == []


def test_outcome_and_poll_language_detected():
    assert critic.OUTCOME.search("Voters approved the measure in November.")
    assert critic.OUTCOME.search("Polls show the measure ahead.")
    assert not critic.OUTCOME.search("If it passes, the state would borrow $10 billion.")


# ---- Candidate Profiler -----------------------------------------------------------

def test_parse_candidates_keeps_official_order_and_statements():
    lg = parse_ca_candidates((FIX / "ca_lt-governor_statements.txt").read_text(encoding="utf-8"))
    assert [(c["name"], c["party"], c["has_statement"]) for c in lg] == [
        ("Fiona Ma", "Democratic", True), ("Gloria Romero", "Republican", True)]
    ag = parse_ca_candidates((FIX / "ca_attorney-general_statements.txt").read_text(encoding="utf-8"))
    assert [(c["name"], c["has_statement"]) for c in ag] == [("Rob Bonta", False), ("Michael E. Gates", True)]


def test_race_cards_treat_candidates_equally():
    for name in ("CA-2026-11-03-lt-governor.json", "CA-2026-11-03-attorney-general.json"):
        rec = json.loads((CARDS / name).read_text(encoding="utf-8"))
        card = RaceCard(**rec["card"])
        checks = critic.race_code_checks(card)
        assert critic.hard_failures_race(checks) == []
        for c in card.candidates:
            if c.says_basis == "none_found":
                assert not c.says and c.core_case is None      # no guessing someone's views
            else:
                assert 2 <= len(c.says) <= 4 and c.core_case


def test_unequal_space_is_flagged():
    rec = json.loads((CARDS / "CA-2026-11-03-lt-governor.json").read_text(encoding="utf-8"))
    card = RaceCard(**rec["card"])
    card.candidates[0].core_case = " ".join(["word"] * 300)
    assert any("Unequal space" in f for f in critic.hard_failures_race(critic.race_code_checks(card)))
