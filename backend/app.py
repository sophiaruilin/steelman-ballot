"""Steelman Ballot web app: FastAPI backend + the mobile-first frontend in /frontend.

    uvicorn backend.app:app --port 8020          (from the steelman-ballot folder)

SNAPSHOT_ONLY=1 (default) serves only cards already researched (output/cards/) and never calls a
model, so the public site can't spend tokens. SNAPSHOT_ONLY=0 researches missing measures on demand
through the shared per-contest cache (backend/pipeline.get_measure), within the spending caps.

Privacy: addresses are sent in the request BODY (POST), never in a URL, so they don't appear in
browser history or server/proxy access logs (and uvicorn runs with --no-access-log). They are used
once to look up districts with the Census Geocoder and are never logged, stored or returned.
A ZIP code alone also works: it gives the statewide measures for the covered states.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
from collections import defaultdict, deque
from datetime import date

import segno
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles

from backend import config
from backend.agents.ballot_mapper import COVERED_STATES, MAP_KIND, measures_for, races_for
from backend.share import open_graph, share_text, whatsapp_link
from backend.sources.geocoder import AddressNotFound, Area, Jurisdiction, geocode
from backend.sources.http import SourceError
from backend.sources.web import WebReader

FRONTEND = config.ROOT / "frontend"
CARDS = config.ROOT / "output" / "cards"
ELECTION = os.getenv("ELECTION", "2026-11-03")
SNAPSHOT_ONLY = os.getenv("SNAPSHOT_ONLY", "1") != "0"
CARD_ID = re.compile(r"^[A-Z]{2}-\d{4}-\d{2}-\d{2}-[a-z0-9-]{1,40}$")

app = FastAPI(title="Steelman Ballot", docs_url=None, redoc_url=None)

# ---- Security headers (no third-party scripts, styles, fonts or frames) ---------------

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; manifest-src 'self'; worker-src 'self'; base-uri 'none'; "
       "form-action 'self'; frame-ancestors 'none'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = CSP
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    # App code and styles: always re-check with the server (cheap 304s) so updates show at once.
    if request.url.path.endswith((".js", ".css", ".html", ".webmanifest")) or request.url.path == "/":
        resp.headers["Cache-Control"] = "no-cache"
    elif request.url.path.startswith("/fonts/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


# ---- Per-visitor rate limit (Safety: overspending / abuse) -------------------------------

_hits: dict[str, deque] = defaultdict(deque)
RATE = (30, 60.0)   # 30 ballot lookups per visitor per minute


def rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "?"
    q, now = _hits[ip], time.monotonic()
    while q and now - q[0] > RATE[1]:
        q.popleft()
    if len(q) >= RATE[0]:
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
    q.append(now)


# ---- Cards -----------------------------------------------------------------------------

TOPICS = {
    "Housing": r"hous|rent|home|mortgage|homeless",
    "Taxes": r"tax|revenue|spending limit|audit",
    "Schools": r"school|education|college|universit|student",
    "Health care": r"health|clinic|medical|immunolog|hospital",
    "Elections": r"elect|vot|recall|campaign|ballot",
    "Environment": r"environment|climate|water|land use|ceqa|wildfire",
    "Public safety": r"crime|police|prison|safety|theft|drug",
    "State budget": r"bond|budget|rainy day|reserve|debt",
}


def topics_for(card: dict) -> list[str]:
    text = " ".join([card.get("plain_title", ""), card.get("official_title", ""),
                     *(r.get("topic", "") for r in card.get("what_changes", []))]).lower()
    return [t for t, pat in TOPICS.items() if re.search(pat, text)]


def load_card(card_id: str) -> dict | None:
    if not CARD_ID.match(card_id):
        return None
    p = CARDS / f"{card_id}.json"
    if not p.exists():
        return None
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec.pop("review_rounds", None)   # internal Critic notes aren't part of the public card
    return rec


def measure_summary(card_id: str, number: str, official_title: str) -> dict:
    rec = load_card(card_id)
    if not rec:
        return {"id": card_id, "kind": "measure", "number": number, "official_title": official_title,
                "status": "not_researched"}
    c = rec["card"]
    return {"id": card_id, "kind": "measure", "number": c["number"], "official_title": c["official_title"],
            "plain_title": c["plain_title"], "reading_minutes": c.get("reading_minutes", 2),
            "verified": rec.get("steelman_verified", False), "topics": topics_for(c), "status": "ready"}


_measure_lists: dict[tuple, tuple[float, list, str]] = {}


def ballot_measures(j) -> tuple[list, str]:
    """Official measure list for this voter's state (and city, for NYC), cached for 6 hours."""
    key = (j.state_abbr, j.place.geoid if (j.place and j.state_abbr == "NY") else "", ELECTION)
    hit = _measure_lists.get(key)
    if hit and time.time() - hit[0] < 6 * 3600:
        return hit[1], hit[2]
    measures, status = measures_for(j, ELECTION, WebReader())
    _measure_lists[key] = (time.time(), measures, status)
    return measures, status


CA_STATEWIDE = [("governor", "Governor"), ("lt-governor", "Lieutenant Governor"), ("sos", "Secretary of State"),
                ("controller", "Controller"), ("treasurer", "Treasurer"), ("attorney-general", "Attorney General"),
                ("insurance-commissioner", "Insurance Commissioner"),
                ("superintendent", "Superintendent of Public Instruction")]


def race_summaries(j) -> list[dict]:
    out = []
    if j.state_abbr == "CA":
        for slug, office in CA_STATEWIDE:
            cid = f"CA-{ELECTION}-{slug}"
            rec = load_card(cid)
            out.append({"id": cid, "kind": "race", "office": office, "level": "State executive",
                        "status": "ready" if rec else "not_researched",
                        "candidates": [c["name"] for c in rec["card"]["candidates"]] if rec else []})
    for r in races_for(j, ELECTION):
        out.append({"id": None, "kind": "race", "office": r.office,
                    "level": "Federal" if r.level == "federal" else "State legislature",
                    "status": "not_researched" if r.confirmed else "check_official_ballot", "candidates": []})
    return out


# ---- API -----------------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"ok": True, "snapshot_only": SNAPSHOT_ONLY, "election": ELECTION}


def assemble_ballot(j, measures, mstatus) -> dict:
    mlist = [{**measure_summary(f"{j.state_abbr}-{ELECTION}-{m.slug}", m.number, m.official_title), "scope": m.scope}
             for m in measures]
    return {
        "election": ELECTION,
        "election_passed": date.fromisoformat(ELECTION) < date.today(),
        "state": j.state_abbr,
        "districts": {k: v for k, v in {
            "Congress": j.congressional_district and j.congressional_district.name,
            "State Senate": j.state_senate and j.state_senate.name,
            "State House / Assembly": j.state_house and j.state_house.name,
            "County": j.county and j.county.name,
            "City": j.place and j.place.name}.items() if v},
        "covered_state": j.state_abbr in COVERED_STATES,
        "coverage_note": COVERED_STATES.get(j.state_abbr, "Not covered yet: we show your districts and races only."),
        "coverage": {
            "Ballot measures": mstatus,
            "Statewide offices": "official" if j.state_abbr == "CA" else "not_mapped",
            "Federal": "partial",
            "Local": "official" if any(m.scope != "statewide" for m in measures) else "not_mapped",
        },
        "measures": mlist,
        "races": race_summaries(j),
        "official_links": [
            {"label": "Find your official election office (vote.gov)", "url": "https://vote.gov/"},
            *([{"label": "California Official Voter Information Guide",
                "url": "https://voterguide.sos.ca.gov/"}] if j.state_abbr == "CA" else []),
        ],
        "note": "Confirm against your county's official sample ballot. If anything here disagrees with it, "
                "the official ballot is right.",
    }


def guide_source(j) -> str:
    """Which official source step 2 reads, named for the voter (shown in the progress steps)."""
    if j.state_abbr == "CA":
        return "California Secretary of State: Official Voter Information Guide"
    if j.state_abbr == "MA":
        return "Massachusetts Secretary of the Commonwealth: Information for Voters (PDF)"
    if j.state_abbr == "NY":
        return "NYC Votes (New York City)" if (j.place and j.place.geoid == "3651000") else "New York: statewide proposals"
    if j.state_abbr == "CT":
        return "Connecticut: statewide questions"
    return ""


class Lookup(BaseModel):
    address: str = Field(..., min_length=5, max_length=200)


# ZIP-only lookups: the first three digits of a ZIP code tell us the state (and New York City),
# which is all statewide measures depend on. Only the covered states are mapped.
ZIP3 = {"CA": [(900, 961)], "MA": [(10, 27), (55, 55)], "NY": [(5, 5), (100, 149)], "CT": [(60, 69)]}
STATE_INFO = {"CA": ("California", "06"), "MA": ("Massachusetts", "25"), "NY": ("New York", "36"), "CT": ("Connecticut", "09")}
NYC_ZIP3 = {100, 101, 102, 103, 104, 111, 112, 113, 114, 116}
ZIP_RE = re.compile(r"^\s*(\d{5})(?:-\d{4})?\s*$")


def zip_jurisdiction(zip5: str) -> Jurisdiction:
    z3 = int(zip5[:3])
    state = next((st for st, ranges in ZIP3.items() if any(lo <= z3 <= hi for lo, hi in ranges)), None)
    if not state:
        raise AddressNotFound("A ZIP code alone works for the states we cover (California, Massachusetts, "
                              "New York, Connecticut). Elsewhere, enter a street address to see your districts.")
    name, fips = STATE_INFO[state]
    place = Area("New York city", "3651000") if state == "NY" and z3 in NYC_ZIP3 else None
    return Jurisdiction(matched_address="", state_name=name, state_abbr=state, state_fips=fips, county=None,
                        county_subdivision=None, place=place, congressional_district=None, state_senate=None,
                        state_house=None, school_district=None, congress_label="")


def resolve(address: str) -> tuple[Jurisdiction, bool]:
    m = ZIP_RE.match(address)
    if m:
        return zip_jurisdiction(m.group(1)), True
    return geocode(address), False


def with_zip_note(data: dict, zip_only: bool) -> dict:
    data["zip_only"] = zip_only
    if zip_only:
        data["coverage"]["Federal"] = "needs_address"
        data["coverage"]["Local"] = data["coverage"]["Local"] if data["coverage"]["Local"] == "official" else "needs_address"
    return data


@app.post("/api/ballot")
def ballot(request: Request, body: Lookup):
    rate_limit(request)
    try:
        j, zip_only = resolve(body.address)
    except AddressNotFound as e:
        raise HTTPException(404, str(e)) from None
    except SourceError:
        raise HTTPException(503, "The address lookup service is busy. Please try again shortly.") from None
    try:
        measures, mstatus = ballot_measures(j)
    except SourceError:
        measures, mstatus = [], "unavailable"
    return with_zip_note(assemble_ballot(j, measures, mstatus), zip_only)


@app.post("/api/ballot/stream")
async def ballot_stream(request: Request, body: Lookup):
    """Same as /api/ballot, but streams real progress (Server-Sent Events format) so voters can see each step."""
    rate_limit(request)
    address = body.address

    def ev(kind: str, **data) -> str:
        return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def steps():
        t0 = time.monotonic()
        yield ev("step", id="districts", state="start")
        try:
            j, zip_only = await run_in_threadpool(resolve, address)
        except AddressNotFound as e:
            yield ev("fail", message=str(e)); return
        except Exception:
            yield ev("fail", message="The address lookup service is busy. Please try again shortly."); return
        yield ev("step", id="districts", state="done", seconds=round(time.monotonic() - t0, 1),
                 detail=j.state_abbr, zip_only=zip_only)

        src = guide_source(j)
        t1 = time.monotonic()
        yield ev("step", id="guide", state="start", source=src)
        try:
            measures, mstatus = await run_in_threadpool(ballot_measures, j)
        except Exception:
            measures, mstatus = [], "unavailable"
        yield ev("step", id="guide", state="done", seconds=round(time.monotonic() - t1, 1), source=src, count=len(measures))

        t2 = time.monotonic()
        yield ev("step", id="cards", state="start")
        data = with_zip_note(await run_in_threadpool(assemble_ballot, j, measures, mstatus), zip_only)
        ready = sum(m["status"] == "ready" for m in data["measures"])
        yield ev("step", id="cards", state="done", seconds=round(time.monotonic() - t2, 1), count=ready)
        yield ev("ballot", **data)

    return StreamingResponse(steps(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/coverage")
def coverage():
    """States we cover, for the map on the home page."""
    return {"states": COVERED_STATES, "kinds": MAP_KIND, "election": ELECTION}


@app.get("/api/card/{card_id}")
def card(card_id: str, lang: str = Query("en", pattern="^(en|es|zh)$")):
    rec = load_card(card_id)
    if not rec:
        raise HTTPException(404, "This card hasn't been researched yet.")
    rec["lang"] = "en"
    if lang != "en" and "steelman_yes" in rec["card"]:
        from backend.agents.translator import I18N, apply
        tpath = I18N / f"{card_id}.{lang}.json"
        if tpath.exists():
            rec["card"] = apply(rec["card"], json.loads(tpath.read_text(encoding="utf-8")))
            rec["lang"] = lang
            rec["translation_scope"] = "key_points"   # evidence details and sources stay in English
    return rec


def public_base(request: Request) -> str:
    return (os.getenv("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")


@app.get("/api/share/{card_id}")
def share(card_id: str, request: Request):
    rec = load_card(card_id)
    if not rec or "steelman_yes" not in rec["card"]:
        raise HTTPException(404, "Only measure cards can be shared.")
    url = f"{public_base(request)}/c/{card_id}"
    c = rec["card"]
    return {"url": url, "whatsapp_link": whatsapp_link(c, url),
            "whatsapp": share_text(c, url, "whatsapp"), "wechat": share_text(c, url, "wechat"),
            "plain": share_text(c, url, "plain")}


@app.get("/api/qr/{card_id}.svg")
def qr(card_id: str, request: Request):
    if not load_card(card_id):
        raise HTTPException(404)
    svg = segno.make(f"{public_base(request)}/c/{card_id}", error="m").svg_inline(scale=6, border=2)
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/c/{card_id}", response_class=HTMLResponse)
def share_page(card_id: str, request: Request):
    """Lightweight page behind shared links: link previews (Open Graph) + both sides + open the full card."""
    rec = load_card(card_id)
    if not rec or "steelman_yes" not in rec["card"]:
        raise HTTPException(404)
    c, url, e = rec["card"], f"{public_base(request)}/c/{card_id}", html.escape
    tags = "\n".join(f'<meta property="{k}" content="{e(v)}">' for k, v in open_graph(c, url).items())
    # Same rule as the card: No on the left, Yes on the right.
    sides = [("The strongest case against · No", c["steelman_no"]["headline"]),
             ("The strongest case for · Yes", c["steelman_yes"]["headline"])]
    body = "".join(f'<section class="side"><h2>{e(t)}</h2><p>{e(h)}</p></section>' for t, h in sides)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(c['number'])}: {e(c['plain_title'])} | Steelman Ballot</title>
<meta name="description" content="{e(open_graph(c, url)['og:description'])}">
{tags}
<link rel="stylesheet" href="/app.css"></head>
<body class="share-page"><main class="wrap">
<p class="brand">Steelman Ballot</p>
<h1>{e(c['number'])}: {e(c['plain_title'])}</h1>
<div class="sides">{body}</div>
<p class="crux"><b>Where they disagree:</b> {e(c['crux']['text'])}</p>
<p><a class="btn" href="/#card={e(card_id)}">Open the full card: what changes, more reasons, sources</a></p>
<p class="muted">We never tell you how to vote. Not affiliated with any campaign or government.</p>
</main></body></html>"""
    return HTMLResponse(page)


# ---- Frontend -------------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def service_worker():
    # served from the root so it can cache the whole app for offline reading
    return FileResponse(FRONTEND / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=FRONTEND), name="static")


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail or "Not found"}, status_code=exc.status_code)
