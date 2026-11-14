"""The card format: What-changes table, parallel headlines, on-the-merits rule, reading level."""

import pytest

from backend.agents import critic
from backend.models import ChangeRow, Claim, Crux, MeasureCard, Steelman

SRC = "https://voterguide.sos.ca.gov/propositions/9/analysis.htm"


def claim(text, label="fact", whose=None):
    return Claim(text=text, label=label, whose=whose, source_url=SRC)


def side(name, headline, topic="State cost", reasons=1):
    return Steelman(
        side=name, basis="official_argument", headline=headline, headline_topic=topic,
        more_reasons=[f"{name} reason {i}." for i in range(reasons)],
        values=["Cost"], best_evidence=[claim(f"{name} point.", "value", name)],
        who_it_helps="Taxpayers.", answer_to_other_side="They reply on the merits.")


def card(yes_headline="Supporters argue it would build more parks in cities that need them.",
         no_headline="Opponents argue it would cost the state money it needs for schools.", rows=3):
    return MeasureCard(
        measure_id="CA-2026-11-03-prop-9", number="Prop 9", official_title="PARKS BOND.",
        plain_title="Borrow money for city parks", title_disputed=False, put_on_ballot_by="Legislature",
        yes_means="The state would borrow money to build parks.", no_means="The state would not borrow this money.",
        what_changes=[ChangeRow(topic=t, today="No new money.", if_passes="Up to $2 billion for parks.",
                                label="fact", source_url=SRC) for t in ["State cost", "Parks built", "Who decides"][:rows]],
        who_is_affected=["City residents"], fiscal_impact=claim("About $100 million a year.", "prediction", "Legislative Analyst"),
        steelman_yes=side("Yes", yes_headline), steelman_no=side("No", no_headline),
        crux=Crux(kind="values", text="Parks now versus other needs."), evidence=[claim("Cities have fewer parks.")],
        reading_minutes=2)


def test_good_card_has_no_hard_failures():
    assert critic.hard_failures(critic.code_checks(card())) == []


def test_motive_and_funder_arguments_are_rejected():
    bad = card(no_headline="Opponents argue it is a power grab funded by billionaires and special interests.")
    checks = critic.code_checks(bad)
    assert {"power grab", "funded by", "billionaires", "special interests"} <= set(checks["motive_or_funder"])
    assert any("on the merits" in f for f in critic.hard_failures(checks))


def test_substantive_concern_is_allowed():
    ok = card(no_headline="Opponents argue it would make it harder for some eligible voters to have ballots counted.")
    assert critic.code_checks(ok)["motive_or_funder"] == []


def test_headline_length_and_parallel_rules():
    long = card(yes_headline=" ".join(["word"] * 30) + ".")
    fails = critic.structural_failures(critic.code_checks(long))
    assert any("at most 25 words" in f for f in fails)
    assert any("similar in length" in f for f in fails)


def test_headline_topic_must_match_a_change_row():
    c = card()
    c.steelman_yes.headline_topic = "Something else"
    assert any("headline_topic" in f for f in critic.structural_failures(critic.code_checks(c)))


@pytest.mark.parametrize("rows,ok", [(2, False), (3, True)])
def test_what_changes_needs_3_to_5_rows(rows, ok):
    fails = critic.structural_failures(critic.code_checks(card(rows=rows)))
    assert (not any("3-5 rows" in f for f in fails)) is ok


def test_judgment_calls_are_not_structural():
    # motive wording and reading level go through the Critic loop (badge), not the writer validator (crash)
    bad = card(no_headline="Opponents argue it is a power grab funded by billionaires and special interests.")
    assert not any("on the merits" in f for f in critic.structural_failures(critic.code_checks(bad)))


def test_reading_grade_plain_vs_legalese():
    plain = "The state would borrow money to build homes. People with low incomes could rent them."
    legal = ("Authorizes issuance of general obligation bonds notwithstanding constitutional appropriation "
             "limitations and intergovernmental administrative requirements.")
    assert critic.reading_grade(plain) < 6 < 14 < critic.reading_grade(legal)


def test_hard_to_read_card_is_flagged():
    c = card()
    c.yes_means = ("Authorizes issuance of general obligation bonds notwithstanding constitutional appropriation "
                   "limitations and intergovernmental administrative requirements applicable to municipalities.")
    c.no_means = c.yes_means
    for r in c.what_changes:
        r.if_passes = c.yes_means
    assert any("reading grade" in f for f in critic.hard_failures(critic.code_checks(c)))
