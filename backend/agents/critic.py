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
# Arguments about the other side's motives, character, funders or party labels: not about the change.
MOTIVE = re.compile(
    r"\b(power[- ]grab|billionaires?|millionaires?|donors?|bankroll\w*|funded by|financed by|special[- ]interests?|"
    r"self[- ]serving|corrupt\w*|lobbyists?|maga|trump|biden|newsom|republicans? (want|are trying)|"
    r"democrats? (want|are trying)|politicians? (want|are trying) to protect|insiders?|elites?)\b", re.IGNORECASE)

HEADLINE_MAX_WORDS = 25
TARGET_GRADE = 9.0        # reading level the plan promises (about 8th-9th grade)


class Score(BaseModel):
    score: int = Field(ge=1, le=5)
    reason: str


class CriticVerdict(BaseModel):
    turing_yes: Score = Field(description="Ideological Turing Test for the Yes side (on the merits of the change).")
    turing_no: Score = Field(description="Ideological Turing Test for the No side (on the merits of the change).")
    swap_test_pass: bool
    swap_notes: list[str] = Field(default_factory=list)
    fidelity_problems: list[str] = Field(default_factory=list)
    label_problems: list[str] = Field(default_factory=list)
    loaded_or_overconfident: list[str] = Field(default_factory=list)
    off_the_merits: list[str] = Field(default_factory=list, description="Points about motives, funders, character "
                                      "or party labels instead of the change.")
    never_list: list[str] = Field(default_factory=list)
    false_balance: list[str] = Field(default_factory=list)
    verdict: Literal["pass", "revise"]
    instructions: str = Field(default="", description="Numbered, concrete edits if verdict is revise.")


# ---- Readability (Flesch-Kincaid grade, no dependencies) -----------------------------

def _syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def reading_grade(text: str) -> float:
    """Flesch-Kincaid grade level of a passage (0 if too short to judge)."""
    sentences = [s for s in re.split(r"[.!?;:]+\s", text.strip()) if s.strip()]
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if len(words) < 8:
        return 0.0
    syl = sum(_syllables(w) for w in words)
    return round(0.39 * len(words) / max(1, len(sentences)) + 11.8 * syl / len(words) - 15.59, 1)


def headline_text(card: MeasureCard) -> str:
    """What a voter sees first: title, yes/no, the What-changes table and both headlines."""
    rows = [f"{r.topic}. Today: {r.today}. If it passes: {r.if_passes}." for r in card.what_changes]
    return " ".join([card.plain_title + ".", card.yes_means, card.no_means, *rows,
                     card.steelman_yes.headline, card.steelman_no.headline])


# ---- Code checks ------------------------------------------------------------------

def _side_text(s: Steelman) -> str:
    return " ".join([s.headline, *s.more_reasons, *s.values, *(c.text for c in s.best_evidence),
                     s.who_it_helps, s.answer_to_other_side])


def code_checks(card: MeasureCard) -> dict:
    yes, no = _side_text(card.steelman_yes), _side_text(card.steelman_no)
    wy, wn = len(yes.split()), len(no.split())
    hy, hn = len(card.steelman_yes.headline.split()), len(card.steelman_no.headline.split())
    sides_text = yes + " " + no
    all_text = json.dumps(card.model_dump(), ensure_ascii=False)
    topics = {r.topic.strip().lower() for r in card.what_changes}
    return {
        "words": {"yes": wy, "no": wn, "ratio": round(max(wy, wn) / max(1, min(wy, wn)), 2)},
        "headline_words": {"yes": hy, "no": hn},
        "headline_topics_ok": all(s.headline_topic.strip().lower() in topics
                                  for s in (card.steelman_yes, card.steelman_no)),
        "what_changes_rows": len(card.what_changes),
        "more_reasons": {"yes": len(card.steelman_yes.more_reasons), "no": len(card.steelman_no.more_reasons)},
        "evidence_points": {"yes": len(card.steelman_yes.best_evidence), "no": len(card.steelman_no.best_evidence)},
        "certainty_words": {"yes": len(CERTAINTY.findall(yes)), "no": len(CERTAINTY.findall(no))},
        "reading_grade": reading_grade(headline_text(card)),
        "loaded_words": sorted({m.group(0).lower() for m in LOADED.finditer(all_text)}),
        "motive_or_funder": sorted({m.group(0).lower() for m in MOTIVE.finditer(sides_text)}),
        "recommendation": sorted({m.group(0) for m in RECOMMEND.finditer(all_text)}),
        "outcome_or_polls": sorted({m.group(0) for m in OUTCOME.finditer(all_text)}),
        "instruction_like_text": find_injection(all_text),
    }


STRUCTURAL = ("Headlines must", "Make the two headlines", "Each headline_topic", "What changes needs",
              "At most 2 more_reasons", "Give both sides the same number")


def structural_failures(checks: dict) -> list[str]:
    """Format rules the writer can always satisfy (checked in the writer's own validator)."""
    return [f for f in hard_failures(checks) if f.startswith(STRUCTURAL)]


def hard_failures(checks: dict) -> list[str]:
    """Problems that fail a card no matter what the model critic says."""
    out = []
    if checks["recommendation"]:
        out.append(f"Remove vote recommendations: {checks['recommendation']}")
    if checks["outcome_or_polls"]:
        out.append(f"Remove election outcomes or polls: {checks['outcome_or_polls']}")
    if checks["instruction_like_text"]:
        out.append(f"Remove instruction-like text copied from a source: {checks['instruction_like_text']}")
    if checks["motive_or_funder"]:
        out.append(f"Keep the steelmen on the merits of the change: remove motive/funder/party points "
                   f"({checks['motive_or_funder']}) and use the substantive concern underneath.")
    if checks["words"]["ratio"] > 1.6:
        out.append(f"Sides are unbalanced in length (Yes {checks['words']['yes']} words, No {checks['words']['no']}). "
                   f"Bring them within about 30% of each other.")
    hw = checks["headline_words"]
    if max(hw.values()) > HEADLINE_MAX_WORDS:
        out.append(f"Headlines must be at most {HEADLINE_MAX_WORDS} words (Yes {hw['yes']}, No {hw['no']}).")
    if abs(hw["yes"] - hw["no"]) > 8:
        out.append(f"Make the two headlines similar in length (Yes {hw['yes']} words, No {hw['no']}).")
    if not checks["headline_topics_ok"]:
        out.append("Each headline_topic must exactly match the topic of a What-changes row.")
    if not 3 <= checks["what_changes_rows"] <= 5:
        out.append("What changes needs 3-5 rows.")
    if max(checks["more_reasons"].values()) > 2:
        out.append("At most 2 more_reasons per side.")
    if checks["evidence_points"]["yes"] != checks["evidence_points"]["no"]:
        out.append("Give both sides the same number of evidence points.")
    if checks["reading_grade"] > TARGET_GRADE + 2:
        out.append(f"Plainer words and shorter sentences in the title, yes/no, What-changes rows and headlines "
                   f"(reading grade {checks['reading_grade']}; target about {TARGET_GRADE:.0f}).")
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
        verdict.instructions = ("Automatic checks:\n" + "\n".join(f"- {h}" for h in hard)
                                + ("\nCritic:\n" + verdict.instructions if verdict.instructions else ""))
    if verdict.verdict == "pass" and min(verdict.turing_yes.score, verdict.turing_no.score) < 4:
        verdict.verdict = "revise"   # enforce the rule even if the model is lenient
    return verdict, checks, result.usage


# ---- Race cards: equal-treatment and never-list checks (code only) -------------------

def race_code_checks(card) -> dict:
    all_text = json.dumps(card.model_dump(), ensure_ascii=False)
    with_stmt = [c for c in card.candidates if c.says_basis != "none_found"]
    words = {c.name: len(" ".join([c.headline or "", c.core_case or "", *(s.text for s in c.says)]).split())
             for c in with_stmt}
    cand_text = " ".join(" ".join([c.headline or "", c.core_case or "", *(s.text for s in c.says)])
                         for c in card.candidates)
    return {
        "candidates": len(card.candidates),
        "with_statements": len(with_stmt),
        "words": words,
        "word_ratio": round(max(words.values()) / max(1, min(words.values())), 2) if len(words) > 1 else 1.0,
        "headline_words": {c.name: len((c.headline or "").split()) for c in with_stmt},
        "reading_grade": reading_grade(" ".join(c.headline or "" for c in with_stmt)),
        "loaded_words": sorted({m.group(0).lower() for m in LOADED.finditer(all_text)}),
        "attacks_or_funders": sorted({m.group(0).lower() for m in MOTIVE.finditer(cand_text)}),
        "recommendation": sorted({m.group(0) for m in RECOMMEND.finditer(all_text)}),
        "outcome_or_polls": sorted({m.group(0) for m in OUTCOME.finditer(all_text)}),
        "instruction_like_text": find_injection(all_text),
    }


def hard_failures_race(checks: dict) -> list[str]:
    out = [f"{k}: {checks[k]}" for k in ("recommendation", "outcome_or_polls", "instruction_like_text",
                                         "attacks_or_funders") if checks[k]]
    if checks["headline_words"] and max(checks["headline_words"].values()) > HEADLINE_MAX_WORDS:
        out.append(f"Headlines must be at most {HEADLINE_MAX_WORDS} words: {checks['headline_words']}")
    if checks["word_ratio"] > 1.6:
        out.append(f"Unequal space between candidates: {checks['words']}")
    return out
