"""Shared settings for Steelman Ballot: paths, keys, model, cache policy and spending limits."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent          # steelman-ballot/backend
ROOT = HERE.parent                              # steelman-ballot
PROMPTS_DIR = HERE / "prompts"
CACHE_DIR = Path(os.getenv("STEELMAN_CACHE_DIR") or ROOT / "data" / "cache")

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
load_dotenv(ROOT / ".env")         # steelman-ballot/.env
load_dotenv(ROOT.parent / ".env")  # fallback: a .env one folder up

# ---- Source API keys ------------------------------------------------------
DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY", "").strip()      # OpenFEC + Congress.gov
OPENSTATES_API_KEY = os.getenv("OPENSTATES_API_KEY", "").strip()
CENSUS_API_KEY = os.getenv("CENSUS_API_KEY", "").strip()           # ACS demographics
VOTESMART_API_KEY = os.getenv("VOTESMART_API_KEY", "").strip()

HTTP_TIMEOUT_S = 20.0
USER_AGENT = "SteelmanBallot/0.1 (nonpartisan student project)"

# ---- Models (chosen from the CA look-back evaluation, output/eval/summary.md) ----
# Writers (Measure Analyst, Candidate Profiler) and the eval Grader: gpt-6-astra, the strongest
# reasoning model. A gpt-6-luna writer was about as accurate but needed 2 rewrites on every
# measure, passed the steelman tests less often, and used ~1.7x input / ~2.1x output tokens.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-astra").strip() or "gpt-6-astra"
REASONING_EFFORT = "medium"
# Critic: gpt-6-luna. A second model's perspective on the writer's blind spots; it caught the
# sabotaged test card and subtle overstatements, and code-level hard rules back it up.
CRITIC_MODEL = os.getenv("CRITIC_MODEL", "gpt-6-luna").strip() or "gpt-6-luna"
# Translator and simple extraction (e.g. reading a measure list from an official page): gpt-6-luna.
LIGHT_MODEL = os.getenv("LIGHT_MODEL", "gpt-6-luna").strip() or "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")

# ---- Spending guards ------------------------------------------------------
DAILY_TOKEN_CAP = int(os.getenv("DAILY_TOKEN_CAP", "2000000"))
BALLOT_TOKEN_BUDGET = int(os.getenv("BALLOT_TOKEN_BUDGET", "250000"))
MAX_CRITIC_ROUNDS = int(os.getenv("MAX_CRITIC_ROUNDS", "3"))   # rewrites a card may get before the "unverified" badge

# ---- Cache / refresh policy (see cache.py) --------------------------------
# days-to-election threshold -> (full refresh every N days, change-check every N hours)
REFRESH_POLICY = [
    (60, 7, 24),   # 60+ days out: weekly full refresh, daily change check
    (0, 1, 1),     # inside 60 days: daily full refresh, hourly change check
]


def llm_provider() -> str:
    """'openai' (your own key, direct) or 'portkey' (class key). LLM_PROVIDER overrides."""
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit in ("openai", "portkey"):
        return explicit
    return "openai" if os.getenv("OPENAI_API_KEY", "").strip() else "portkey"


def build_model(model_name: str | None = None):
    """Model + settings for an agent (OpenAI Responses API, medium reasoning), via your own
    OpenAI key when OPENAI_API_KEY is set, otherwise via the class Portkey key."""
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
    from pydantic_ai.providers.openai import OpenAIProvider

    settings = OpenAIResponsesModelSettings(openai_reasoning_effort=REASONING_EFFORT)
    if llm_provider() == "openai":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set (see .env.example).")
        client = AsyncOpenAI(api_key=key, max_retries=2)
        return OpenAIResponsesModel(model_name or MODEL_NAME, provider=OpenAIProvider(openai_client=client)), settings

    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY (your own key) or PORTKEY_API_KEY (class key) in .env.")
    client = AsyncOpenAI(
        api_key="unused",  # Portkey authenticates with the header below
        base_url=PORTKEY_BASE_URL,
        default_headers={
            "x-portkey-api-key": api_key,
            "x-portkey-provider": "openai",
            # Freshness is handled by OUR jurisdiction cache; never replay a stale Portkey answer.
            "x-portkey-cache-force-refresh": "true",
        },
    )
    model = OpenAIResponsesModel(model_name or MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    return model, settings
