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
    assert client.get("/api/ballot", params={"address": "abc"}).status_code == 422


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(app_module, "RATE", (2, 60.0))
    app_module._hits.clear()
    monkeypatch.setattr(app_module, "geocode", lambda a: (_ for _ in ()).throw(app_module.AddressNotFound("x")))
    codes = [client.get("/api/ballot", params={"address": "123 Main St"}).status_code for _ in range(3)]
    assert codes == [404, 404, 429]
    app_module._hits.clear()


def test_service_worker_never_caches_ballot_lookups():
    sw = client.get("/sw.js").text
    assert 'url.pathname.startsWith("/api/")) return;' in sw


def test_coverage_endpoint_lists_three_states():
    states = client.get("/api/coverage").json()["states"]
    assert set(states) == {"CA", "MA", "NY"} and "New York City" in states["NY"]


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
