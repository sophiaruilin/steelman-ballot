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


class Steelman(BaseModel):
    """One side's case, stated the way its own most thoughtful supporters would state it."""

    side: str = Field(description="'Yes' or 'No' for a measure.")
    basis: Literal["official_argument", "named_advocates", "no_organized_side"] = Field(
        description="Where this case comes from: the official ballot argument; other named supporters/opponents "
                    "found on allowed sources; or no organized side exists, so the case is built from the "
                    "trade-offs in the nonpartisan analysis (say so in core_claim).")
    top_points: list[str] = Field(
        default_factory=list,
        description="This side's 3 most important distinct points from its official argument AND rebuttal "
                    "(or from named advocates), each one short sentence in that side's own framing. "
                    "Empty only if basis is no_organized_side.")
    core_claim: str = Field(description="What this side wants, in one sentence.")
    values: list[str] = Field(description="1-3 values this side cares about (e.g. fairness, cost, local control).")
    best_evidence: list[Claim] = Field(description="2-4 of this side's strongest supporting points, each cited.")
    who_it_helps: str = Field(description="Which people this side says benefit, in their view.")
    answer_to_other_side: str = Field(description="This side's best reply to the OTHER side's strongest objection.")


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
    yes_means: str = Field(description="What happens if it passes.")
    no_means: str = Field(description="What happens if it fails (the status quo).")
    who_is_affected: list[str] = Field(description="2-5 groups most directly affected, neutrally described.")
    fiscal_impact: Claim = Field(description="Cost/savings estimate from the official nonpartisan analyst, labeled prediction.")
    steelman_yes: Steelman
    steelman_no: Steelman
    crux: Crux
    evidence: list[Claim] = Field(description="'What the evidence says': 2-5 neutral facts from official/nonpartisan "
                                  "sources that bear on the disputed points. Not arguments.")
    supporters: list[str] = Field(default_factory=list, description="Named supporters listed in official sources.")
    opponents: list[str] = Field(default_factory=list, description="Named opponents listed in official sources.")
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
    core_case: str | None = Field(default=None, description="Their best case for themselves in one or two sentences, "
                                  "as their most thoughtful supporters would put it. None if none_found.")
    priorities: list[str] = Field(default_factory=list, description="1-3 priorities they name, in their terms.")


class RaceCard(BaseModel):
    race_id: str
    office: str
    what_office_does: Claim = Field(description="One or two sentences from the official source on what this office does.")
    candidates: list[CandidateProfile] = Field(description="Every candidate, in the official order given.")
    where_they_differ: Crux | None = Field(default=None, description="Where the candidates' stated priorities really "
                                           "differ, if their statements allow it. None if fewer than two have statements.")
