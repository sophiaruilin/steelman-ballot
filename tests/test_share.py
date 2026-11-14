"""Sharing must always include both sides, and fit each chat app's formatting."""

import json
from pathlib import Path
from urllib.parse import unquote

from backend.share import FOOTER, open_graph, share_text, whatsapp_link

CARD = json.loads((Path(__file__).parent.parent / "output" / "cards" / "CA-2026-11-03-prop-3.json")
                  .read_text(encoding="utf-8"))["card"]
URL = "https://steelman-ballot.onrender.com/c/CA-2026-11-03-prop-3"


def test_every_share_contains_both_sides_and_footer():
    for ch in ("whatsapp", "wechat", "plain"):
        t = share_text(CARD, URL, ch)
        assert "Strongest case for YES" in t and "Strongest case for NO" in t
        assert FOOTER in t and URL in t
        assert len(t) <= 900


def test_wechat_text_has_no_formatting_symbols():
    t = share_text(CARD, URL, "wechat")
    assert "*" not in t


def test_whatsapp_uses_bold_and_wa_me_link():
    assert "*Strongest case for" in share_text(CARD, URL, "whatsapp")
    link = whatsapp_link(CARD, URL)
    assert link.startswith("https://wa.me/?text=") and "Strongest case for NO" in unquote(link)


def test_order_alternates_by_measure_number():
    odd = share_text({**CARD, "number": "Prop 3"}, URL)
    even = share_text({**CARD, "number": "Prop 4"}, URL)
    assert odd.index("for YES") < odd.index("for NO")
    assert even.index("for NO") < even.index("for YES")


def test_link_preview_names_both_sides():
    tags = open_graph(CARD, URL)
    assert "Yes and for No" in tags["og:description"] and len(tags["og:description"]) <= 190
