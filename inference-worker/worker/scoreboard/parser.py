"""Turn OCR tokens from the scoreboard area into a score, or nothing.

Broadcast scoreboards show two numbers, often with a league logo between them
that OCR reads as a "0" ("302" for 3-2, or "03" for the right-hand 3). Team
names, sponsors and the match clock around it are ignored. When in doubt the
result is no score: a goal is only confirmed from repeated clean readings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MIN_CONFIDENCE = 0.6
MAX_GOALS = 15  # a higher number is a misread, not a football score
_SCORE_TEXT = re.compile(r"(?<!\d)(\d{1,2})\s*[-–—:]\s*(\d{1,2})(?!\d)")
_LOGO_DIGIT = "0"


@dataclass(frozen=True, slots=True)
class Token:
    text: str
    x: float  # horizontal centre in the image
    confidence: float


@dataclass(frozen=True, slots=True)
class Reading:
    home: int | None
    away: int | None
    goal_banner: bool


def parse_reading(tokens: list[Token]) -> Reading:
    usable = [t for t in tokens if t.confidence >= MIN_CONFIDENCE and t.text.strip()]
    banner = any("GOAL" in t.text.upper() for t in usable)
    score = _score(usable)
    if score is None:
        return Reading(None, None, banner)
    return Reading(score[0], score[1], banner)


def _score(tokens: list[Token]) -> tuple[int, int] | None:
    for token in tokens:
        match = _SCORE_TEXT.search(token.text)
        if match:
            return _plausible(int(match[1]), int(match[2]))
    digits = sorted((t for t in tokens if t.text.strip().isdigit()), key=lambda t: t.x)
    if len(digits) >= 2:
        left, right = digits[0].text.strip(), digits[-1].text.strip()
        return _plausible(_side(left, logo_at_end=True), _side(right, logo_at_end=False))
    if len(digits) == 1:
        text = digits[0].text.strip()
        if len(text) == 3 and text[1] == _LOGO_DIGIT:  # digit, logo, digit
            return _plausible(int(text[0]), int(text[2]))
    return None


def _side(text: str, *, logo_at_end: bool) -> int:
    """One team's number; a two-character token may include the logo's "0"."""
    if len(text) == 2 and logo_at_end and text.endswith(_LOGO_DIGIT):
        return int(text[0])
    if len(text) == 2 and not logo_at_end and text.startswith(_LOGO_DIGIT):
        return int(text[1])
    return int(text)


def _plausible(home: int, away: int) -> tuple[int, int] | None:
    return (home, away) if 0 <= home <= MAX_GOALS and 0 <= away <= MAX_GOALS else None
