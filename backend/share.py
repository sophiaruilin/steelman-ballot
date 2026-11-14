"""Share text for WhatsApp, WeChat and the phone's share sheet. A shared card ALWAYS shows both sides.

    from backend.share import share_text
    share_text(card, url, channel="whatsapp")   # *bold* formatting, wa.me link
    share_text(card, url, channel="wechat")     # plain text, no formatting symbols

Neutrality rule: there is no way to share one side alone. Both steelmen's one-line core claims,
the crux, and "We never tell you how to vote" are always included, in Yes/No order alternated by
card number (the same alternation the dashboard uses).
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

FOOTER = "Steelman Ballot: the strongest case for every side. We never tell you how to vote."
MAX_CHARS = 900   # comfortable in one chat bubble


def _clip(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def yes_first(card: dict) -> bool:
    digits = "".join(ch for ch in card.get("number", "") if ch.isdigit())
    return int(digits or 0) % 2 == 1    # odd-numbered measures show Yes first, even show No first


def share_text(card: dict, url: str, channel: Literal["whatsapp", "wechat", "plain"] = "plain") -> str:
    b = (lambda s: f"*{s}*") if channel == "whatsapp" else (lambda s: s)
    yes = ("Strongest case for YES", card["steelman_yes"]["core_claim"])
    no = ("Strongest case for NO", card["steelman_no"]["core_claim"])
    first, second = (yes, no) if yes_first(card) else (no, yes)
    lines = [
        b(f"{card['number']}: {_clip(card['plain_title'], 90)}"),
        "",
        f"{b(first[0])}: {_clip(first[1], 220)}",
        f"{b(second[0])}: {_clip(second[1], 220)}",
        "",
        f"{b('Where they disagree')}: {_clip(card['crux']['text'], 200)}",
        "",
        f"Both sides, sources and what the evidence says: {url}",
        FOOTER,
    ]
    text = "\n".join(lines)
    return text if len(text) <= MAX_CHARS else text[: MAX_CHARS - 1] + "…"


def whatsapp_link(card: dict, url: str) -> str:
    """Opens WhatsApp (app or web) with the message ready to send to any chat."""
    return "https://wa.me/?text=" + quote(share_text(card, url, "whatsapp"))


def open_graph(card: dict, url: str, image_url: str | None = None) -> dict[str, str]:
    """Link-preview tags (WhatsApp, iMessage, Slack...). The description names both sides."""
    tags = {
        "og:type": "article",
        "og:title": f"{card['number']}: {_clip(card['plain_title'], 80)}",
        "og:description": _clip("The strongest case for Yes and for No, with sources. "
                                f"Where they disagree: {card['crux']['text']}", 190),
        "og:url": url,
        "og:site_name": "Steelman Ballot",
    }
    if image_url:
        tags["og:image"] = image_url
    return tags
