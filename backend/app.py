"""Steelman Ballot web app: FastAPI backend + the mobile-first frontend in /frontend.

    uvicorn backend.app:app --port 8020          (from the steelman-ballot folder)

SNAPSHOT_ONLY=1 (default) serves only cards already researched (output/cards/) and never calls a
model, so the public site can't spend tokens. SNAPSHOT_ONLY=0 researches missing measures on demand
through the shared per-contest cache (backend/pipeline.get_measure), within the spending caps.

Privacy: addresses are used only to look up districts with the Census Geocoder. They are never
logged, stored or returned; responses contain district names only.
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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from backend import config
from backend.agents.ballot_mapper import STATE_GUIDES, races_for
from backend.share import open_graph, share_text, whatsapp_link
from backend.sources.geocoder import AddressNotFound, geocode
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


_measure_lists: dict[tuple, tuple[float, list]] = {}


def state_measures(state: str) -> list:
    """Official measure list for a state, cached for 6 hours (one fetch serves everyone)."""
    key = (state, ELECTION)
    hit = _measure_lists.get(key)
    if hit and time.time() - hit[0] < 6 * 3600:
        return hit[1]
    guide = STATE_GUIDES.get(state)
    measures = guide(WebReader(), ELECTION) if guide else []
    _measure_lists[key] = (time.time(), measures)
    return measures


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


@app.get("/api/ballot")
def ballot(request: Request, address: str = Query(..., min_length=5, max_length=200)):
    rate_limit(request)
    try:
        j = geocode(address)
    except AddressNotFound as e:
        raise HTTPException(404, str(e)) from None
    except SourceError:
        raise HTTPException(503, "The address lookup service is busy. Please try again shortly.") from None
    try:
        measures = state_measures(j.state_abbr)
    except SourceError:
        measures = []
    mlist = [measure_summary(f"{j.state_abbr}-{ELECTION}-prop-{m.number.split()[-1]}", m.number, m.official_title)
             for m in measures]
    races = race_summaries(j)
    ready = [m for m in mlist if m["status"] == "ready"] + [r for r in races if r["status"] == "ready"]
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
        "coverage": {
            "Statewide measures": "official" if mlist else "not_mapped",
            "Statewide offices": "official" if j.state_abbr == "CA" else "not_mapped",
            "Federal": "partial",
            "Local": "not_mapped",
        },
        "measures": mlist,
        "races": races,
        "minutes_to_read": sum(m.get("reading_minutes", 2) for m in ready),
        "official_links": [
            {"label": "Find your official election office (vote.gov)", "url": "https://vote.gov/"},
            *([{"label": "California Official Voter Information Guide",
                "url": "https://voterguide.sos.ca.gov/"}] if j.state_abbr == "CA" else []),
        ],
        "note": "Confirm against your county's official sample ballot. If anything here disagrees with it, "
                "the official ballot is right.",
    }


@app.get("/api/card/{card_id}")
def card(card_id: str):
    rec = load_card(card_id)
    if not rec:
        raise HTTPException(404, "This card hasn't been researched yet.")
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
    sides = [("Strongest case for YES", c["steelman_yes"]["headline"]), ("Strongest case for NO", c["steelman_no"]["headline"])]
    if not (int(re.sub(r"\D", "", c["number"]) or 0) % 2):
        sides.reverse()
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
