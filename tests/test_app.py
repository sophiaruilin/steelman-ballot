"""Web app tests (offline: card, share, QR, security; the ballot lookup needs the network)."""

import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.app import app, topics_for

client = TestClient(app)
CARD = "CA-2026-11-03-prop-3"


def test_home_page_and_security_headers():
    r = client.get("/")
    assert r.status_code == 200 and "Steelman Ballot" in r.text
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-inline" not in csp
    assert r.headers["x-content-type-options"] == "nosniff"


def test_card_api_hides_internal_critic_notes():
    r = client.get(f"/api/card/{CARD}")
    assert r.status_code == 200
    body = r.json()
    assert "steelman_yes" in body["card"] and "review_rounds" not in body


@pytest.mark.parametrize("bad", ["..%2F..%2F.env", "not-a-card", "CA-2026-11-03-PROP-3<script>"])
def test_card_ids_are_validated(bad):
    assert client.get(f"/api/card/{bad}").status_code == 404


def test_share_api_always_returns_both_sides():
    s = client.get(f"/api/share/{CARD}").json()
    for ch in ("whatsapp", "wechat", "plain"):
        assert "Strongest case for YES" in s[ch] and "Strongest case for NO" in s[ch]
    assert "*" not in s["wechat"] and s["whatsapp_link"].startswith("https://wa.me/?text=")


def test_race_cards_cannot_be_shared_as_measures():
    assert client.get("/api/share/CA-2026-11-03-lt-governor").status_code == 404


def test_qr_code_svg():
    r = client.get(f"/api/qr/{CARD}.svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and "<svg" in r.text


def test_share_page_has_link_preview_and_escapes_text():
    r = client.get(f"/c/{CARD}")
    assert r.status_code == 200
    assert 'property="og:description"' in r.text
    # same fixed rule as the card: No (against) on the left, Yes (for) on the right
    assert r.text.index("The strongest case against · No") < r.text.index("The strongest case for · Yes")
    assert "We never tell you how to vote" in r.text
    assert "<script" not in r.text            # no scripts at all on the share page


def test_topics_drive_order_only():
    assert "Taxes" in topics_for({"plain_title": "Make existing higher income tax rates permanent"})
    assert "Elections" in topics_for({"plain_title": "Require government ID checks for voting"})


def test_ballot_rejects_bad_address_input():
    assert client.post("/api/ballot", json={"address": "abc"}).status_code == 422


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(app_module, "RATE", (2, 60.0))
    app_module._hits.clear()
    monkeypatch.setattr(app_module, "geocode", lambda a: (_ for _ in ()).throw(app_module.AddressNotFound("x")))
    codes = [client.post("/api/ballot", json={"address": "123 Main St"}).status_code for _ in range(3)]
    assert codes == [404, 404, 429]
    app_module._hits.clear()


def test_service_worker_never_caches_ballot_lookups():
    sw = client.get("/sw.js").text
    assert 'url.pathname.startsWith("/api/")) return;' in sw


def test_coverage_endpoint_lists_three_states():
    states = client.get("/api/coverage").json()["states"]
    assert set(states) == {"CA", "MA", "NY", "CT"} and "New York City" in states["NY"]
    assert client.get("/api/coverage").json()["kinds"]["CT"] == "checked"


def test_site_pages_and_fonts_are_self_hosted():
    html = client.get("/").text
    for section in ('id="view-how"', 'id="view-steelman"', 'id="view-philosophy"', "Think more deeply."):
        assert section in html
    assert "fonts.googleapis" not in html and "cdn." not in html
    assert client.get("/fonts/eb-garamond-latin-500-normal.woff2").status_code == 200
    css = client.get("/app.css").text
    assert "#234742" in css and "#F4F0E7" in css
    # no partisan red or blue anywhere in the palette
    import re
    for hexcode in re.findall(r"#[0-9a-fA-F]{6}\b", css):
        r, g, b = (int(hexcode[i:i + 2], 16) for i in (1, 3, 5))
        assert not (r > 150 and g < 90 and b < 90), f"red-ish {hexcode}"
        assert not (b > 150 and r < 90 and g < 120), f"blue-ish {hexcode}"


def test_every_interface_string_exists_in_all_three_languages():
    import json, re
    js = client.get("/i18n.js").text
    body = js[js.index("window.I18N = ") + len("window.I18N = "): js.rstrip().rindex("}") + 1]
    # the dictionary is plain JSON-like JS: quote the language keys and drop trailing commas
    body = re.sub(r"\b(en|es|zh):", r'"\1":', body)
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    d = json.loads(body)
    assert set(d["en"]) == set(d["es"]) == set(d["zh"])
    html = client.get("/").text
    for key in re.findall(r'data-i18n(?:-placeholder)?="([^"]+)"', html):
        assert key in d["en"], key
    assert html.count('data-langblock="es"') == 3 and html.count('data-langblock="zh"') == 3


def test_card_api_serves_translation_when_available(tmp_path, monkeypatch):
    import json
    from backend.agents import translator
    monkeypatch.setattr(translator, "I18N", tmp_path)
    rec = client.get(f"/api/card/{CARD}").json()
    from backend.agents.translator import key_layer
    t = key_layer(rec["card"])
    t["plain_title"] = "Título traducido"
    (tmp_path / f"{CARD}.es.json").write_text(json.dumps({"translated": t}), encoding="utf-8")
    es = client.get(f"/api/card/{CARD}", params={"lang": "es"}).json()
    assert es["lang"] == "es" and es["card"]["plain_title"] == "Título traducido"
    assert es["card"]["evidence"] == rec["card"]["evidence"]          # details stay in English
    assert client.get(f"/api/card/{CARD}", params={"lang": "zh"}).json()["lang"] == "en"   # not translated yet
    assert client.get(f"/api/card/{CARD}", params={"lang": "fr"}).status_code == 422


def test_ballot_stream_reports_real_steps_in_order(monkeypatch):
    import json
    from backend.sources.geocoder import parse
    from pathlib import Path
    j = parse(json.loads((Path(__file__).parent / "fixtures" / "census_new_haven.json").read_text(encoding="utf-8")))
    monkeypatch.setattr(app_module, "geocode", lambda a: j)
    monkeypatch.setattr(app_module, "ballot_measures", lambda jj: ([], "none_on_ballot"))
    app_module._hits.clear()
    r = client.post("/api/ballot/stream", json={"address": "165 Church St, New Haven, CT 06510"})
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [(blk.split("\n")[0][len("event: "):], json.loads(blk.split("\n")[1][len("data: "):]))
              for blk in r.text.strip().split("\n\n")]
    kinds = [(k, d.get("id"), d.get("state")) if k == "step" else (k, None, None) for k, d in events]
    assert kinds == [("step", "districts", "start"), ("step", "districts", "done"),
                     ("step", "guide", "start"), ("step", "guide", "done"),
                     ("step", "cards", "start"), ("step", "cards", "done"), ("ballot", None, None)]
    assert events[2][1]["source"] == "Connecticut: statewide questions"
    assert events[-1][1]["state"] == "CT" and "measures" in events[-1][1]


def test_ballot_stream_bad_address_fails_cleanly(monkeypatch):
    monkeypatch.setattr(app_module, "geocode", lambda a: (_ for _ in ()).throw(app_module.AddressNotFound("No match")))
    app_module._hits.clear()
    r = client.post("/api/ballot/stream", json={"address": "123 Nowhere Lane"})
    assert "event: fail" in r.text and "No match" in r.text and "event: ballot" not in r.text


def test_addresses_never_go_in_a_url():
    # Lookups are POST-only: a GET with ?address= is refused, so addresses can't land in logs or history.
    assert client.get("/api/ballot", params={"address": "1315 10th St, Sacramento, CA"}).status_code in (404, 405)
    assert client.get("/api/ballot/stream", params={"address": "1315 10th St, Sacramento, CA"}).status_code in (404, 405)
    js = client.get("/app.js").text
    assert "/api/ballot?address" not in js and "ballot/stream?address" not in js


@pytest.mark.parametrize("zip5,state,nyc", [("95814", "CA", False), ("02139", "MA", False), ("10007", "NY", True),
                                            ("12207", "NY", False), ("06510", "CT", False)])
def test_zip_only_lookup(zip5, state, nyc):
    j, zip_only = app_module.resolve(zip5)
    assert zip_only and j.state_abbr == state and (j.place is not None and j.place.geoid == "3651000") == nyc
    assert j.congressional_district is None   # no street address, so no district races


def test_zip_outside_covered_states_is_explained():
    with pytest.raises(app_module.AddressNotFound, match="street address"):
        app_module.resolve("78701")   # Austin, TX


def test_render_runs_without_access_logs():
    from pathlib import Path
    assert "--no-access-log" in (Path(__file__).parent.parent / "render.yaml").read_text(encoding="utf-8")


# ---- Anonymous usage totals ----------------------------------------------------------------

def test_lookup_counts_state_only_never_the_address(monkeypatch):
    import json
    from pathlib import Path
    from backend import stats
    from backend.sources.geocoder import parse
    stats._mem.clear()
    j = parse(json.loads((Path(__file__).parent / "fixtures" / "census_new_haven.json").read_text(encoding="utf-8")))
    monkeypatch.setattr(app_module, "geocode", lambda a: j)
    monkeypatch.setattr(app_module, "ballot_measures", lambda jj: ([], "none_on_ballot"))
    app_module._hits.clear()
    secret = "165 Church St, New Haven, CT 06510"
    assert client.post("/api/ballot", json={"address": secret}).status_code == 200
    totals = stats.report()["total"]
    assert totals["lookup"] == {"all": 1, "CT": 1}
    dumped = json.dumps({k: dict(v) for k, v in stats._mem.items()})
    assert "Church" not in dumped and "06510" not in dumped and "165" not in dumped


def test_card_views_languages_and_shares_are_counted():
    from backend import stats
    stats._mem.clear()
    client.get(f"/api/card/{CARD}", params={"lang": "es"})
    client.get(f"/api/share/{CARD}", params={"ch": "wechat"})
    t = stats.report()["total"]
    assert t["card"][CARD] == 1 and t["lang"]["es"] == 1 and t["share"]["wechat"] == 1
    assert client.get(f"/api/share/{CARD}", params={"ch": "evil<script>"}).status_code == 422


def test_counter_refuses_anything_but_plain_labels():
    from backend import stats
    stats._mem.clear()
    stats.count("lookup:CA", "lookup:123 Main St, Springfield", "note:<b>x</b>", "visit")
    assert dict(stats._mem["total"]) == {"lookup:CA": 1, "visit": 1}


def test_stats_page_is_public_and_anonymous():
    r = client.get("/stats")
    assert r.status_code == 200 and "Anonymous usage" in r.text and "noindex" in r.text
    j = client.get("/api/stats").json()
    assert j["storage"] in ("memory", "upstash") and "no addresses" in j["note"]


def test_stats_page_survives_a_bad_upstash_setting(monkeypatch):
    from backend import stats
    monkeypatch.setattr(stats, "URL", "https://example.upstash.io")
    monkeypatch.setattr(stats, "TOKEN", "bad-token")
    def boom(keys):
        raise stats.StatsUnavailable("Upstash returned HTTP 401: Unauthorized")
    monkeypatch.setattr(stats, "_hgetall_many", boom)
    r = client.get("/stats")
    assert r.status_code == 200 and "Totals unavailable" in r.text and "bad-token" not in r.text
    assert client.get("/api/stats").json()["error"].startswith("Totals unavailable")
