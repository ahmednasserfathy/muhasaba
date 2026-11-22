"""Pure scoring over trusted, day-pinned definitions, never a filtered UI list."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal


@dataclass(frozen=True)
class ItemProgress:
    code: str
    target_count: int
    completed_count: int = 0
    source_type: Literal["OFFICIAL", "PERSONAL"] = "OFFICIAL"
    is_score_eligible: bool = True
    hidden: bool = False
    sort_order: int = 0


@dataclass(frozen=True)
class Score:
    earned: Fraction
    possible: Fraction
    status: Literal["PENDING", "PARTIAL", "COMPLETED", "EXCLUDED"]


@dataclass(frozen=True)
class DayScore:
    earned: Fraction
    possible: Fraction
    percent: Fraction | None


def score_card(
    points: int,
    kind: Literal["TOGGLE", "FASTING", "ADHKAR_SET"],
    *,
    completed: bool = False,
    eligible: bool = True,
    items: tuple[ItemProgress, ...] = (),
) -> Score:
    """Eligibility is supplied by the day policy (fasting/date rules come later).

    Personal entries are always ignored, even if erroneously flagged eligible.
    Counts are defensively clamped; write APIs must reject out-of-range counts.
    """
    if type(points) is not int or points < 0:
        raise ValueError("points must be a non-negative integer")
    if kind not in ("TOGGLE", "FASTING", "ADHKAR_SET"):
        raise ValueError("unknown activity kind")
    if type(completed) is not bool or type(eligible) is not bool:
        raise ValueError("completed and eligible must be booleans")
    if not eligible:
        return Score(Fraction(0), Fraction(0), "EXCLUDED")
    if kind == "ADHKAR_SET":
        if completed:
            raise ValueError("set completion is derived from official counters")
        official = []
        seen = set()
        for item in items:
            if item.source_type not in ("OFFICIAL", "PERSONAL"):
                raise ValueError("unknown item source")
            if item.source_type != "OFFICIAL" or not item.is_score_eligible:
                continue
            if item.code in seen:
                raise ValueError("duplicate official scoring item")
            seen.add(item.code)
            if type(item.target_count) is not int or not 1 <= item.target_count <= 1000:
                raise ValueError("target count must be an integer in [1, 1000]")
            if type(item.completed_count) is not int:
                raise ValueError("completed count must be an integer")
            official.append(
                Fraction(
                    min(max(item.completed_count, 0), item.target_count),
                    item.target_count,
                )
            )
        if not official:
            raise ValueError("a scored set requires official score-eligible items")
        fraction = sum(official, Fraction(0)) / len(official)
    else:
        if items:
            raise ValueError("only adhkar sets have item counters")
        fraction = Fraction(int(completed))
    status = "COMPLETED" if fraction == 1 else "PENDING" if fraction == 0 else "PARTIAL"
    return Score(points * fraction, Fraction(points), status)


def score_day(cards: tuple[Score, ...]) -> DayScore:
    earned = sum((card.earned for card in cards), Fraction(0))
    possible = sum((card.possible for card in cards), Fraction(0))
    return DayScore(earned, possible, 100 * earned / possible if possible else None)


def display_percent(percent: Fraction | None) -> int | None:
    """Round half up only at the presentation boundary, with no float conversion."""
    if percent is None:
        return None
    return (2 * percent.numerator + percent.denominator) // (2 * percent.denominator)
