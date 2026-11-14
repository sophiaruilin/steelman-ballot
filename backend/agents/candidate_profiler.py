"""Candidate Profiler: one race -> RaceCard (Says + steelman per candidate), then code adds Did / Funded by.

    python -m backend.agents.candidate_profiler CA lt-governor
    python -m backend.agents.candidate_profiler CA attorney-general

Candidate lists and order come from the official source (parsed in code, not by the model);
the output validator rejects any card that drops, adds or reorders candidates or treats them unequally.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from functools import lru_cache

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.usage import UsageLimits

from backend import config
from backend.agents import critic
from backend.agents.common import ResearchDeps, check_claims, fetch_page, log_run, usage_dict
from backend.models import RaceCard
from backend.sources.web import WebReader

RACE_LIMITS = UsageLimits(request_limit=12, total_tokens_limit=120_000)

CA_OFFICES = {
    "governor": "Governor", "lt-governor": "Lieutenant Governor", "sos": "Secretary of State",
    "controller": "Controller", "treasurer": "Treasurer", "attorney-general": "Attorney General",
    "insurance-commissioner": "Insurance Commissioner", "superintendent": "Superintendent of Public Instruction",
}


def parse_ca_candidates(text: str) -> list[dict]:
    """[{name, party, has_statement}] in official (randomized-drawing) order."""
    body = text[: text.find("Back to the Top")] if "Back to the Top" in text else text
    out = []
    for m in re.finditer(r"(?m)^([A-Z][^\n|]{2,60}) \| ([A-Z][A-Z ]+)$", body):
        name, party = m.group(1).strip(), m.group(2).strip().title()
        out.append({"name": name, "party": party,
                    "has_statement": not body[m.end():m.end() + 40].strip().startswith("No candidate statement")})
    return out


@lru_cache(maxsize=1)
def get_agent() -> Agent[ResearchDeps, RaceCard]:
    model, settings = config.build_model()
    agent = Agent(model, name="candidate_profiler", deps_type=ResearchDeps, output_type=RaceCard,
                  instructions=(config.PROMPTS_DIR / "candidate_profiler.md").read_text(encoding="utf-8"),
                  model_settings=settings, tools=[fetch_page], retries=3)

    @agent.output_validator
    def validate(ctx: RunContext[ResearchDeps], card: RaceCard) -> RaceCard:
        expected = ctx.deps.__dict__.get("expected_candidates") or []
        problems = []
        got = [c.name for c in card.candidates]
        want = [c["name"] for c in expected]
        if want and got != want:
            problems.append(f"Candidates must be exactly {want} in this order (got {got}).")
        claims = [card.what_office_does] + [s for c in card.candidates for s in c.says]
        problems += check_claims(claims, ctx.deps.fetched)
        with_stmt = [c for c in card.candidates if c.says_basis != "none_found"]
        for c in card.candidates:
            if c.says_basis == "none_found" and (c.says or c.core_case):
                problems.append(f"{c.name} has no statement: leave says empty and core_case null.")
            if c.says_basis != "none_found" and not (2 <= len(c.says) <= 4 and c.core_case):
                problems.append(f"{c.name}: give 2-4 says items and a core_case.")
            for s in c.says:
                if s.label != "fact" or s.whose:
                    continue
                problems.append(f"{c.name}: self-reported facts need `whose` (the candidate's own statement).")
        if len(with_stmt) > 1 and max(len(c.says) for c in with_stmt) - min(len(c.says) for c in with_stmt) > 1:
            problems.append("Give candidates with statements the same number of says items.")
        if problems:
            raise ModelRetry("Fix these problems and return the card again:\n- " + "\n- ".join(problems[:8]))
        return card

    return agent


async def profile_ca_statewide(office_slug: str, reader: WebReader | None = None) -> dict:
    reader = reader or WebReader()
    url = f"https://voterguide.sos.ca.gov/candidates/{office_slug}-candidate-statements.htm"
    cands = parse_ca_candidates(reader.fetch(url).data["text"])
    deps = ResearchDeps(reader=reader)
    deps.expected_candidates = cands  # used by the validator
    race_id = f"CA-2026-11-03-{office_slug}"
    office = CA_OFFICES.get(office_slug, office_slug)
    prompt = (f"Race: California {office}, general election 2026-11-03. race_id='{race_id}', office='{office}'.\n"
              f"Candidates in official order: " + "; ".join(f"{c['name']} ({c['party']})" for c in cands)
              + f"\nFetch the official candidate statements page: {url}")
    t0 = time.time()
    result = await get_agent().run(prompt, deps=deps, usage_limits=RACE_LIMITS)
    card = result.output
    checks = critic.race_code_checks(card)
    usage = usage_dict(result.usage)
    record = {
        "race_id": race_id,
        "card": card.model_dump(),
        "ballot_order_note": "Official order (California assigns it by randomized drawing).",
        # Code-filled sections. California statewide offices are financed under state law (Cal-Access),
        # which isn't connected yet; candidates without a legislative record have no "Did" section.
        "did": {c.name: None for c in card.candidates},
        "funded_by": {c.name: {"status": "not_connected", "note": "State campaign finance (Cal-Access) not connected yet."}
                      for c in card.candidates},
        "checks": checks,
        "sources": list(deps.fetched),
        "meta": {"seconds": round(time.time() - t0, 1), "usage_by_model": {config.MODEL_NAME: usage}},
    }
    log_run({"agent": "candidate_profiler", "race_id": race_id, "hard_failures": critic.hard_failures_race(checks),
             **record["meta"]})
    return record


if __name__ == "__main__":
    slug = sys.argv[2] if len(sys.argv) > 2 else "lt-governor"
    rec = asyncio.run(profile_ca_statewide(slug))
    out = config.ROOT / "output" / "cards" / f"{rec['race_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checks": rec["checks"], **rec["meta"]}, indent=2))
    print("saved", out)
