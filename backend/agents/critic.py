"""Fact-Check & Neutrality Critic: automatic checks in code, then the steelman tests by a model.

Code checks (free, deterministic): balance between sides (words, evidence points, certainty words),
loaded words, vote recommendations / election outcomes / polls, and instruction-like text.
Model checks (gpt-6-luna by default): Ideological Turing Test per side, swap test, source
fidelity, labels, false balance. See prompts/critic.md.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from backend import config
from backend.models import MeasureCard, Steelman
from backend.sources.web import fence, find_injection

CRITIC_LIMITS = UsageLimits(request_limit=3, total_tokens_limit=60_000)

LOADED = re.compile(
    r"\b(radical|extreme|common[- ]sense|scheme|giveaway|handout|job[- ]killing|reckless|disastrous|"
    r"devastating|so[- ]called|falsely|admits?|claims?|alleged(ly)?|truth is|obviously|clearly)\b", re.IGNORECASE)
CERTAINTY = re.compile(r"\b(will|definitely|certainly|guarantee[sd]?|always|never|undoubtedly|proven)\b", re.IGNORECASE)
RECOMMEND = re.compile(r"\b((you|voters) should vote|we recommend|vote (yes|no) on|recommend(s|ed)? (a )?(yes|no))\b",
                       re.IGNORECASE)
OUTCOME = re.compile(r"\b(voters (approved|rejected|passed|defeated)|(passed|failed|won|lost) (on|in) (november|the election)|"
                     r"election results?|polls? (show|found|suggest)|leading in|ahead in the polls)\b", re.IGNORECASE)


class Score(BaseModel):
    score: int = Field(ge=1, le=5)
    reason: str


class CriticVerdict(BaseModel):
    turing_yes: Score = Field(description="Ideological Turing Test for the Yes side.")
    turing_no: Score = Field(description="Ideological Turing Test for the No side.")
    swap_test_pass: bool
    swap_notes: list[str] = Field(default_factory=list)
    fidelity_problems: list[str] = Field(default_factory=list)
    label_problems: list[str] = Field(default_factory=list)
    loaded_or_overconfident: list[str] = Field(default_factory=list)
    never_list: list[str] = Field(default_factory=list)
    false_balance: list[str] = Field(default_factory=list)
    verdict: Literal["pass", "revise"]
    instructions: str = Field(default="", description="Numbered, concrete edits if verdict is revise.")


# ---- Code checks ------------------------------------------------------------------

def _side_text(s: Steelman) -> str:
    return " ".join([*s.top_points, s.core_claim, *s.values, *(c.text for c in s.best_evidence), s.who_it_helps, s.answer_to_other_side])


def code_checks(card: MeasureCard) -> dict:
    yes, no = _side_text(card.steelman_yes), _side_text(card.steelman_no)
    wy, wn = len(yes.split()), len(no.split())
    all_text = json.dumps(card.model_dump(), ensure_ascii=False)
    return {
        "words": {"yes": wy, "no": wn, "ratio": round(max(wy, wn) / max(1, min(wy, wn)), 2)},
        "evidence_points": {"yes": len(card.steelman_yes.best_evidence), "no": len(card.steelman_no.best_evidence)},
        "certainty_words": {"yes": len(CERTAINTY.findall(yes)), "no": len(CERTAINTY.findall(no))},
        "loaded_words": sorted({m.group(0).lower() for m in LOADED.finditer(all_text)}),
        "recommendation": sorted({m.group(0) for m in RECOMMEND.finditer(all_text)}),
        "outcome_or_polls": sorted({m.group(0) for m in OUTCOME.finditer(all_text)}),
        "instruction_like_text": find_injection(all_text),
    }


def hard_failures(checks: dict) -> list[str]:
    """Problems that fail a card no matter what the model critic says."""
    out = []
    if checks["recommendation"]:
        out.append(f"Remove vote recommendations: {checks['recommendation']}")
    if checks["outcome_or_polls"]:
        out.append(f"Remove election outcomes or polls: {checks['outcome_or_polls']}")
    if checks["instruction_like_text"]:
        out.append(f"Remove instruction-like text copied from a source: {checks['instruction_like_text']}")
    if checks["words"]["ratio"] > 1.6:
        out.append(f"Sides are unbalanced in length (Yes {checks['words']['yes']} words, No {checks['words']['no']}). "
                   f"Bring them within about 30% of each other.")
    if abs(checks["evidence_points"]["yes"] - checks["evidence_points"]["no"]) > 1:
        out.append("Give both sides the same number of evidence points.")
    return out


# ---- Model critic -------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_agent() -> Agent[None, CriticVerdict]:
    model, settings = config.build_model(config.CRITIC_MODEL)
    return Agent(model, name="critic", output_type=CriticVerdict, model_settings=settings, retries=2,
                 instructions=(config.PROMPTS_DIR / "critic.md").read_text(encoding="utf-8"))


async def review(card: MeasureCard, sources: dict[str, str]) -> tuple[CriticVerdict, dict, object]:
    checks = code_checks(card)
    prompt = (
        "DRAFT CARD (JSON):\n" + json.dumps(card.model_dump(), ensure_ascii=False, indent=1)
        + "\n\nAUTOMATIC CHECKS:\n" + json.dumps(checks)
        + "\n\nSOURCE PAGES THE WRITER READ:\n" + "\n\n".join(fence(u, t) for u, t in sources.items())
    )
    result = await get_agent().run(prompt, usage_limits=CRITIC_LIMITS)
    verdict = result.output
    hard = hard_failures(checks)
    if hard:
        verdict.verdict = "revise"
        verdict.instructions = "\n".join(f"{i}. {h}" for i, h in enumerate(hard, 1)) + (
            "\n" + verdict.instructions if verdict.instructions else "")
    if verdict.verdict == "pass" and min(verdict.turing_yes.score, verdict.turing_no.score) < 4:
        verdict.verdict = "revise"   # enforce the rule even if the model is lenient
    return verdict, checks, result.usage


# ---- Race cards: equal-treatment and never-list checks (code only) -------------------

def race_code_checks(card) -> dict:
    all_text = json.dumps(card.model_dump(), ensure_ascii=False)
    with_stmt = [c for c in card.candidates if c.says_basis != "none_found"]
    words = {c.name: len(" ".join([c.core_case or "", *(s.text for s in c.says)]).split()) for c in with_stmt}
    return {
        "candidates": len(card.candidates),
        "with_statements": len(with_stmt),
        "words": words,
        "word_ratio": round(max(words.values()) / max(1, min(words.values())), 2) if len(words) > 1 else 1.0,
        "loaded_words": sorted({m.group(0).lower() for m in LOADED.finditer(all_text)}),
        "recommendation": sorted({m.group(0) for m in RECOMMEND.finditer(all_text)}),
        "outcome_or_polls": sorted({m.group(0) for m in OUTCOME.finditer(all_text)}),
        "instruction_like_text": find_injection(all_text),
    }


def hard_failures_race(checks: dict) -> list[str]:
    out = [f"{k}: {checks[k]}" for k in ("recommendation", "outcome_or_polls", "instruction_like_text") if checks[k]]
    if checks["word_ratio"] > 1.6:
        out.append(f"Unequal space between candidates: {checks['words']}")
    return out
