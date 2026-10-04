from datetime import date
import pytest
from brolay_stats import (Leg, Week, to_decimal, implied_prob, decimal_to_american,
                          fmt_american, current_streak, longest_streak, HIT, MISS, PUSH)


def leg(person, odds, result=None):
    return Leg(person, f"{person} pick", "spread", odds, result)


def test_odds_conversions():
    assert to_decimal(-110) == pytest.approx(1.9091, abs=1e-4)
    assert to_decimal(150) == 2.5
    assert implied_prob(-110) == pytest.approx(0.5238, abs=1e-4)
    assert implied_prob(150) == pytest.approx(0.4)
    assert decimal_to_american(2.5) == 150
    assert decimal_to_american(1.9091) == -110
    assert fmt_american(150) == "+150" and fmt_american(-110) == "-110"


def test_week1_parlay_price():
    w = Week(1, date(2026, 9, 13), [leg("Matt", -105), leg("Dad", -104),
                                    leg("Nick", -113), leg("Dan", -110)], 40)
    assert w.status == "pending"
    assert w.combined_decimal == pytest.approx(13.781, abs=0.01)
    assert w.combined_american == 1278
    assert w.potential_payout == pytest.approx(551.25, abs=0.5)
    assert w.payout is None and w.net is None


def test_won_lost_push_void():
    won = Week(1, date(2026, 9, 13), [leg("A", -110, HIT), leg("B", 100, HIT)], 40)
    assert won.status == "won"
    assert won.payout == pytest.approx(40 * 1.9091 * 2, abs=0.05)
    lost = Week(2, date(2026, 9, 20), [leg("A", -110, HIT), leg("B", 100, MISS), leg("C", 100, None)], 40)
    assert lost.status == "lost" and lost.payout == 0 and lost.net == -40
    assert [a.person for a in lost.anchors] == ["B"]
    pushed = Week(3, date(2026, 9, 27), [leg("A", -110, HIT), leg("B", 100, PUSH)], 40)
    assert pushed.status == "won"
    assert pushed.payout == pytest.approx(40 * 1.9091, abs=0.05)
    void = Week(4, date(2026, 10, 4), [leg("A", -110, PUSH), leg("B", 100, PUSH)], 40)
    assert void.status == "void" and void.net == 0


def test_mvp_and_blown_layup():
    w = Week(1, date(2026, 9, 13), [leg("A", -200, HIT), leg("B", 250, HIT),
                                    leg("C", -150, MISS), leg("D", 120, MISS)], 40)
    assert w.mvp.person == "B"   # longest odds that hit
    assert w.blown_layup.person == "C"  # safest pick that missed


def test_streaks():
    legs = [leg("A", -110, HIT), leg("A", -110, HIT), leg("A", -110, MISS), leg("A", -110, HIT)]
    assert current_streak(legs) == "W1"
    assert longest_streak(legs, HIT) == 2
    assert current_streak([]) == "-"
    assert current_streak(legs[:3]) == "L1"
