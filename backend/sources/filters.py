"""Small shared filters for source data."""

from __future__ import annotations

import re

# Honorary resolutions (congratulations, memorials, "X Day") say little about a lawmaker's record.
_CEREMONIAL = re.compile(
    r"^\s*(a\s+resolution\s+|relating\s+to\s+(?=designating))?(congratulat|recogniz|commend|honor|in\s+memory|memorializ|celebrat|"
    r"welcom|expressing\s+(gratitude|condolences|support\s+for\s+the\s+designation)|designating\s+.*\s+(day|week|month)\b|"
    r"supporting\s+the\s+designation)",
    re.IGNORECASE,
)


def is_ceremonial(title: str | None) -> bool:
    return bool(title and _CEREMONIAL.search(title))
