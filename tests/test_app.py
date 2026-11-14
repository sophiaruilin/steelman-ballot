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
    assert 'property="og:description"' in r.text and "Strongest case for YES" in r.text
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
