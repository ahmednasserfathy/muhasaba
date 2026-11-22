from dataclasses import replace
from fractions import Fraction

import pytest

from app.modules.catalog.scoring import (
    ItemProgress,
    display_percent,
    score_card,
    score_day,
)


def items(counts, targets=None):
    targets = targets or [1] * len(counts)
    return tuple(
        ItemProgress(str(i), target, count)
        for i, (count, target) in enumerate(zip(counts, targets, strict=True))
    )


@pytest.mark.parametrize("kind", ["TOGGLE", "FASTING"])
def test_completion_and_undo(kind):
    assert [
        score_card(2, kind, completed=value).earned for value in (False, True, False)
    ] == [0, 2, 0]


@pytest.mark.parametrize(
    "counts,expected,status",
    [
        ([0, 0], 0, "PENDING"),
        ([1, 0], 1, "PARTIAL"),
        ([1, 1], 2, "COMPLETED"),
    ],
)
def test_two_item_set(counts, expected, status):
    result = score_card(2, "ADHKAR_SET", items=items(counts))
    assert (result.earned, result.possible, result.status) == (expected, 2, status)


def test_partial_credit_undo_and_customization_neutrality():
    official = items([1, 1, 1, 0, 0])
    baseline = score_card(2, "ADHKAR_SET", items=official)
    assert baseline.earned == Fraction(6, 5)
    hidden = tuple(
        replace(item, hidden=True, sort_order=10 - i)
        for i, item in enumerate(reversed(official))
    )
    # Even a misflagged personal item must contribute exactly zero.
    personal = tuple(
        ItemProgress(f"private-{i}", 1, 1, source_type="PERSONAL") for i in range(10)
    )
    assert score_card(2, "ADHKAR_SET", items=hidden + personal) == baseline
    assert score_card(2, "ADHKAR_SET", items=items([1, 1, 0, 0, 0])).earned == Fraction(
        4, 5
    )
    assert score_card(2, "ADHKAR_SET", items=items([1] * 5)).earned == 2


def test_mixed_targets_and_unrounded_daily_total():
    result = score_card(2, "ADHKAR_SET", items=items([1, 1], [1, 3]))
    assert result.earned == Fraction(4, 3)
    assert score_day((result,) * 3).earned == 4
    assert score_day((result,) * 3).percent == Fraction(200, 3)


@pytest.mark.parametrize(
    "count,expected",
    [(-1, 0), (0, 0), (1, Fraction(2, 3)), (2, Fraction(4, 3)), (3, 2), (4, 2)],
)
def test_defensive_count_clamping(count, expected):
    assert score_card(2, "ADHKAR_SET", items=items([count], [3])).earned == expected


def test_official_non_scoring_items_are_ignored():
    extra = ItemProgress("non-scoring", 1, 1, is_score_eligible=False)
    assert score_card(2, "ADHKAR_SET", items=items([0]) + (extra,)).earned == 0


@pytest.mark.parametrize(
    "entries",
    [
        (),
        (ItemProgress("x", 1, 1, "PERSONAL"),),
        (ItemProgress("x", 1, 1, is_score_eligible=False),),
    ],
)
def test_empty_official_scoring_set_is_configuration_error(entries):
    with pytest.raises(ValueError, match="requires official"):
        score_card(2, "ADHKAR_SET", items=entries)


@pytest.mark.parametrize("target", [0, -1, 1001, True, 1.5])
def test_invalid_target(target):
    with pytest.raises(ValueError, match="target count"):
        score_card(2, "ADHKAR_SET", items=items([0], [target]))


def test_duplicate_membership_and_parent_completion_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        score_card(2, "ADHKAR_SET", items=(ItemProgress("x", 1),) * 2)
    with pytest.raises(ValueError, match="derived"):
        score_card(2, "ADHKAR_SET", completed=True, items=items([0]))


def test_exclusion_and_empty_day():
    excluded = score_card(5, "FASTING", eligible=False, completed=True)
    assert (excluded.earned, excluded.possible, excluded.status) == (0, 0, "EXCLUDED")
    assert score_day((excluded,)).percent is None
    assert display_percent(None) is None


@pytest.mark.parametrize("earned,expected", [(2, 3), (8, 11), (12, 16), (24, 32)])
def test_reference_percent_rounds_only_at_display(earned, expected):
    assert display_percent(Fraction(100 * earned, 74)) == expected
    assert display_percent(Fraction(5, 2)) == 3


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(points=-1),
        dict(points=1.5),
        dict(kind="UNKNOWN"),
        dict(completed=1),
        dict(eligible=1),
    ],
)
def test_invalid_card_inputs(kwargs):
    with pytest.raises(ValueError):
        score_card(**(dict(points=2, kind="TOGGLE") | kwargs))
