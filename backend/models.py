"""Card formats the agents must fill in. A fixed structure is itself a safety control:
an agent can't produce free-form persuasion, only these fields."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """One checkable statement, always tied to a source the agent actually read."""

    text: str = Field(description="The statement, in plain language (8th-grade reading level).")
    label: Literal["fact", "prediction", "value"] = Field(
        description="fact = checkable now; prediction = a forecast (say whose estimate in `whose`); "
                    "value = a judgment about what matters.")
    whose: str | None = Field(default=None, description="For predictions and values: who says so "
                              "(e.g. 'Legislative Analyst', 'supporters', 'opponents').")
    source_url: str = Field(description="URL of a page you fetched with fetch_page that supports this.")
    quote: str | None = Field(default=None, description="Optional exact words copied from that page "
                              "(verbatim, 5-40 words). Leave empty rather than paraphrase.")


class ChangeRow(BaseModel):
    """One row of the "What changes" table: today vs. if the measure passes."""

    topic: str = Field(description="2-5 words naming what changes, e.g. 'Top income tax rate'.")
    today: str = Field(description="Current law or situation, from the nonpartisan analysis (one short sentence).")
    if_passes: str = Field(description="What it would be if the measure passes (one short sentence).")
    label: Literal["fact", "prediction"] = Field(description="fact = what the law would say; prediction = an "
                                                 "estimated effect (set `whose`).")
    whose: str | None = Field(default=None, description="For predictions: whose estimate (e.g. 'Legislative Analyst').")
    source_url: str = Field(description="URL of a page you fetched that supports this row.")


class Steelman(BaseModel):
    """One side's case ON THE MERITS OF THE CHANGE, stated the way its most thoughtful supporters would.

    Effects only: benefits, costs, risks, trade-offs and who is affected. Never the other side's
    motives, character, funders or party labels."""

    side: str = Field(description="'Yes' or 'No' for a measure.")
    basis: Literal["official_argument", "named_advocates", "no_organized_side"] = Field(
        description="Where this case comes from: the official ballot argument; other named supporters/opponents "
                    "found on allowed sources; or no organized side exists, so the case is built from the "
                    "trade-offs in the nonpartisan analysis (say so in the headline).")
    headline: str = Field(description="This side's single strongest point about what the change would do, in one "
                          "plain sentence of at most 25 words. Always shown first.")
    headline_topic: str = Field(description="The `topic` of the What-changes row this headline is about (copy it exactly).")
    more_reasons: list[str] = Field(default_factory=list, description="0-2 further DISTINCT points about the change "
                                    "that this side really makes, one sentence each. Shown behind 'More reasons'.")
    values: list[str] = Field(description="1-3 values this side cares about (e.g. fairness, cost, local control).")
    best_evidence: list[Claim] = Field(description="1-3 cited supporting points for this side's case.")
    who_it_helps: str = Field(description="Which people this side says benefit, in their view.")
    answer_to_other_side: str = Field(description="This side's best reply to the OTHER side's headline, on the merits.")


class Crux(BaseModel):
    kind: Literal["facts", "values", "both"] = Field(description="Is the core disagreement about facts, values, or both?")
    text: str = Field(description="One or two sentences: where the two sides really disagree.")


class MeasureCard(BaseModel):
    measure_id: str = Field(description="e.g. 'CA-2026-11-03-prop-1'")
    number: str = Field(description="e.g. 'Prop 1'")
    official_title: str = Field(description="The official ballot title, copied exactly.")
    plain_title: str = Field(description="A neutral, plain-language title (no loaded words).")
    title_disputed: bool = Field(description="True only if a source says the official title was challenged.")
    put_on_ballot_by: str = Field(description="e.g. 'Legislature' or 'Citizen initiative'.")
    yes_means: str = Field(description="One sentence: what happens if it passes.")
    no_means: str = Field(description="One sentence: what happens if it fails (the status quo).")
    what_changes: list[ChangeRow] = Field(description="3-5 rows: the most important things that would change, "
                                          "today vs. if it passes, from the nonpartisan analysis.")
    who_is_affected: list[str] = Field(description="2-5 groups most directly affected, neutrally described.")
    fiscal_impact: Claim = Field(description="Cost/savings estimate from the official nonpartisan analyst, labeled prediction.")
    steelman_yes: Steelman
    steelman_no: Steelman
    crux: Crux
    evidence: list[Claim] = Field(description="'What the evidence says': 2-5 neutral facts from official/nonpartisan "
                                  "sources that bear on the disputed points. Not arguments.")
    reading_minutes: int = Field(description="Estimated minutes to read this card.")


# ---- Candidate races ------------------------------------------------------------

class CandidateProfile(BaseModel):
    """What a candidate SAYS, and their steelman. "Did" and "Funded by" are filled in by code
    from Congress.gov / Open States / FEC, never written by a model."""

    name: str = Field(description="Exactly as given in the candidate list.")
    party: str
    says_basis: Literal["official_statement", "official_government_site", "none_found"] = Field(
        description="official_statement = the candidate's own statement in the official voter guide; "
                    "official_government_site = their house.gov / senate.gov / state site; none_found = neither.")
    says: list[Claim] = Field(default_factory=list,
                              description="2-4 of the candidate's stated positions or goals, in neutral words, cited. "
                                          "Empty if says_basis is none_found.")
    headline: str | None = Field(default=None, description="The candidate's #1 stated priority, as what they would "
                                 "change or do in office, one sentence of at most 25 words. None if none_found.")
    core_case: str | None = Field(default=None, description="Their best case for themselves in one or two sentences, "
                                  "about their own plans and record (never about opponents). None if none_found.")
    priorities: list[str] = Field(default_factory=list, description="1-3 priorities they name, in their terms.")


class RaceCard(BaseModel):
    race_id: str
    office: str
    what_office_does: Claim = Field(description="One or two sentences from the official source on what this office does.")
    candidates: list[CandidateProfile] = Field(description="Every candidate, in the official order given.")
    where_they_differ: Crux | None = Field(default=None, description="Where the candidates' stated priorities really "
                                           "differ, if their statements allow it. None if fewer than two have statements.")
