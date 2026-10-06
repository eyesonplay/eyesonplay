"""Reading the broadcast scoreboard: parsing OCR tokens and the background reader."""

from __future__ import annotations

import time

import numpy as np
import pytest

from worker.ingest.source import Frame
from worker.scoreboard.parser import Token, parse_reading
from worker.scoreboard.reader import ScoreboardReader


def tokens(*items):
    """(text, x) pairs with full confidence, as the OCR returns them left to right."""
    return [Token(text, x, 1.0) for text, x in items]


@pytest.mark.parametrize(
    ("ocr", "expected"),
    [
        (tokens(("1", 200), ("0", 320)), (1, 0)),  # two clean digits
        (tokens(("MANCHESTER", 80), ("4", 200), ("3", 320)), (4, 3)),  # team name ignored
        (tokens(("302", 260)), (3, 2)),  # league logo between the digits read as "0"
        (tokens(("4", 200), ("03", 300)), (4, 3)),  # logo merged into the right digit
        (tokens(("0", 200), ("0", 260), ("0", 320)), (0, 0)),  # logo read as its own "0"
        (tokens(("ARS 2-1 CHE", 200)), (2, 1)),  # "2-1" style scoreboards
        (tokens(("sky sports", 300), ("4", 200), ("3", 320)), (4, 3)),
    ],
)
def test_scores_are_read_from_ocr_tokens(ocr, expected):
    reading = parse_reading(ocr)

    assert (reading.home, reading.away) == expected
    assert reading.goal_banner is False


def test_the_goal_graphic_is_recognised():
    reading = parse_reading(tokens(("京", 400), ("GOAL", 200)))

    assert reading.goal_banner is True
    assert (reading.home, reading.away) == (None, None)


@pytest.mark.parametrize(
    "ocr",
    [
        tokens(),  # close-up: nothing readable
        tokens(("28'", 100)),  # match clock only
        tokens(("03", 300)),  # half a scoreboard
        tokens(("Revolut", 100), ("OKX", 300)),  # sponsors
        tokens(("4", 200), ("99", 320)),  # implausible score
    ],
)
def test_no_score_is_invented_from_partial_or_unrelated_text(ocr):
    reading = parse_reading(ocr)

    assert (reading.home, reading.away) == (None, None)


def test_low_confidence_text_is_ignored():
    reading = parse_reading([Token("2", 200, 0.3), Token("1", 320, 0.4)])

    assert (reading.home, reading.away) == (None, None)


class FakeOcr:
    """Answers with a score only for the band where the scoreboard is."""

    def __init__(self, band_with_score: int):
        self.band_with_score = band_with_score
        self.calls: list[int] = []

    def __call__(self, image: np.ndarray, band: int) -> list[Token]:
        self.calls.append(band)
        return tokens(("2", 200), ("1", 320)) if band == self.band_with_score else []


def frame(t: float) -> Frame:
    return Frame(int(t * 10), t, 0.0, 1280, 720, np.zeros((720, 1280, 3), np.uint8))


def drain(reader: ScoreboardReader, start: float, seconds: float, step: float = 0.1) -> None:
    t = start
    while t < start + seconds:
        reader.observe(frame(t))
        time.sleep(0.002)  # let the background read finish
        t += step


def test_reader_finds_the_scoreboard_band_and_numbers_each_reading():
    ocr = FakeOcr(band_with_score=1)  # e.g. top-right
    reader = ScoreboardReader(ocr, interval_s=0.5, search_reads=2)

    drain(reader, 0.0, 8.0)
    reader.close()

    latest = reader.latest()
    assert latest is not None and (latest.home, latest.away) == (2, 1)
    assert latest.read_id >= 3
    assert ocr.calls[-3:] == [1, 1, 1]  # settled on the band with the score


def test_reader_reads_at_most_once_per_interval():
    ocr = FakeOcr(band_with_score=0)
    reader = ScoreboardReader(ocr, interval_s=1.0)

    drain(reader, 0.0, 5.0)
    reader.close()

    assert 4 <= len(ocr.calls) <= 6
