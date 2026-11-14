"""Measure Analyst: reads the official pages for one ballot measure and fills in a MeasureCard.

    python -m backend.agents.measure_analyst CA 1      # analyze California Prop 1 (Nov 3, 2026)
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from functools import lru_cache

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.usage import UsageLimits

from backend import config
from backend.agents.common import ResearchDeps, check_claims, fetch_page, log_run, usage_dict
from backend.agents import critic
from backend.models import Claim, MeasureCard
from backend.sources.web import WebReader

PER_MEASURE_LIMITS = UsageLimits(request_limit=14, total_tokens_limit=150_000)


@lru_cache(maxsize=4)
def get_agent(model_name: str | None = None) -> Agent[ResearchDeps, MeasureCard]:
    model, settings = config.build_model(model_name)
    agent = Agent(
        model,
        name="measure_analyst",
        deps_type=ResearchDeps,
        output_type=MeasureCard,
        instructions=(config.PROMPTS_DIR / "measure_analyst.md").read_text(encoding="utf-8"),
        model_settings=settings,
        tools=[fetch_page],
        retries=3,
    )

    @agent.output_validator
    def validate(ctx: RunContext[ResearchDeps], card: MeasureCard) -> MeasureCard:
        problems = []
        claims = [card.fiscal_impact, *card.evidence, *card.steelman_yes.best_evidence, *card.steelman_no.best_evidence]
        problems += check_claims(claims, ctx.deps.fetched)
        rows_as_claims = [Claim(text=r.if_passes, label=r.label, whose=r.whose, source_url=r.source_url)
                          for r in card.what_changes]
        problems += check_claims(rows_as_claims, ctx.deps.fetched)
        if card.fiscal_impact.label == "value":
            problems.append("fiscal_impact must be a 'prediction' (with `whose`), or a 'fact' saying the guide has no estimate.")
        for c in claims + rows_as_claims:
            if c.label in ("prediction", "value") and not c.whose:
                problems.append(f"'{c.text[:50]}...' is a {c.label}: fill in `whose`.")
        # Format rules shared with the Critic. Judgment calls (on-the-merits wording, reading level,
        # balance) go through the Critic's rewrite loop, which ends in an "unverified" badge, not a crash.
        problems += critic.structural_failures(critic.code_checks(card))
        if problems:
            raise ModelRetry("Fix these problems and return the card again:\n- " + "\n- ".join(problems[:8]))
        return card

    return agent


# ---- Where to start for each state's official guide -----------------------------

def ca_urls(prop: str) -> list[str]:
    base = f"https://voterguide.sos.ca.gov/propositions/{prop}/"
    return [base + "title-summary.htm", base + "analysis.htm", base + "arguments-rebuttals.htm"]


def start_urls(state: str, number: str) -> list[str]:
    if state.upper() == "CA":
        return ca_urls(number)
    raise NotImplementedError(f"No official-guide URL pattern for {state} yet; the Ballot Mapper supplies them.")


async def analyze(state: str, number: str, election: str = "2026-11-03",
                  urls: list[str] | None = None, reader: WebReader | None = None) -> tuple[MeasureCard, dict]:
    urls = urls or start_urls(state, number)
    deps = ResearchDeps(reader=reader or WebReader())
    measure_id = f"{state.upper()}-{election}-prop-{number}"
    prompt = (
        f"Measure: {state.upper()} Proposition {number}, election {election}. measure_id = '{measure_id}'.\n"
        f"Start by fetching these official pages:\n" + "\n".join(f"- {u}" for u in urls)
    )
    t0 = time.time()
    result = await get_agent().run(prompt, deps=deps, usage_limits=PER_MEASURE_LIMITS)
    meta = {
        "agent": "measure_analyst",
        "measure_id": measure_id,
        "seconds": round(time.time() - t0, 1),
        "usage": usage_dict(result.usage),
        "pages_read": list(deps.fetched),
        "blocked": deps.blocked,
        "injection_flags": deps.injection_flags,
    }
    log_run(meta)
    return result.output, meta


if __name__ == "__main__":
    state, number = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("CA", "1")
    card, meta = asyncio.run(analyze(state, number))
    out = config.ROOT / "output" / "cards" / f"{card.measure_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"card": card.model_dump(), "meta": meta}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    print(f"card saved to {out}")
