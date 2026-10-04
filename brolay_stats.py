"""Odds math and season statistics for the Brolay tracker.

Pure functions over the JSON data. No PDF code here so it can be tested alone.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

HIT, MISS, PUSH = "hit", "miss", "push"


# ---------------------------------------------------------------- odds math
def to_decimal(odds: int) -> float:
    """American odds to decimal multiplier (stake included)."""
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)


def implied_prob(odds: int) -> float:
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def decimal_to_american(dec: float) -> int:
    if dec >= 2:
        return round((dec - 1) * 100)
    return -round(100 / (dec - 1))


def fmt_american(odds: int) -> str:
    return f"+{odds}" if odds > 0 else str(odds)


# ------------------------------------------------------------------- models
@dataclass
class Leg:
    person: str
    pick: str
    type: str
    odds: int
    result: str | None  # hit | miss | push | None (pending)

    @property
    def decimal(self) -> float:
        return to_decimal(self.odds)

    @property
    def implied(self) -> float:
        return implied_prob(self.odds)

    @property
    def settled(self) -> bool:
        return self.result in (HIT, MISS)


@dataclass
class Week:
    week: int
    date: date
    legs: list[Leg]
    stake: float
    note: str = ""

    @property
    def status(self) -> str:
        """won | lost | pending | void (every leg pushed)."""
        results = [l.result for l in self.legs]
        if MISS in results:
            return "lost"
        if None in results:
            return "pending"
        if all(r == PUSH for r in results):
            return "void"
        return "won"

    @property
    def combined_decimal(self) -> float:
        """Pushed legs drop out; pending legs count as if they hit."""
        dec = 1.0
        for l in self.legs:
            if l.result != PUSH:
                dec *= l.decimal
        return dec

    @property
    def combined_american(self) -> int:
        return decimal_to_american(self.combined_decimal)

    @property
    def potential_payout(self) -> float:
        return self.stake * self.combined_decimal

    @property
    def payout(self) -> float | None:
        if self.status == "won":
            return self.potential_payout
        if self.status == "void":
            return self.stake
        if self.status == "lost":
            return 0.0
        return None

    @property
    def net(self) -> float | None:
        return None if self.payout is None else self.payout - self.stake

    @property
    def anchors(self) -> list[Leg]:
        return [l for l in self.legs if l.result == MISS]

    @property
    def mvp(self) -> Leg | None:
        hits = [l for l in self.legs if l.result == HIT]
        return min(hits, key=lambda l: l.implied) if hits else None

    @property
    def goat(self) -> Leg | None:
        misses = [l for l in self.legs if l.result == MISS]
        return max(misses, key=lambda l: l.implied) if misses else None


@dataclass
class Season:
    year: int
    stake_per_person: float
    members: list[str]
    weeks: list[Week] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Season":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        members = raw["members"]
        stake = raw["stake_per_person"] * len(members)
        weeks = []
        for w in raw["weeks"]:
            legs = [Leg(**l) for l in w["legs"]]
            weeks.append(Week(w["week"], date.fromisoformat(w["date"]), legs,
                              w.get("stake", stake), w.get("note", "")))
        weeks.sort(key=lambda w: w.week)
        return cls(raw["season"], raw["stake_per_person"], members, weeks)

    # ---- group totals
    @property
    def settled_weeks(self) -> list[Week]:
        return [w for w in self.weeks if w.status in ("won", "lost", "void")]

    def record(self) -> dict:
        wins = sum(w.status == "won" for w in self.weeks)
        losses = sum(w.status == "lost" for w in self.weeks)
        pending = sum(w.status == "pending" for w in self.weeks)
        wagered = sum(w.stake for w in self.weeks)
        paid = sum(w.payout for w in self.settled_weeks)
        settled_stake = sum(w.stake for w in self.settled_weeks)
        return dict(wins=wins, losses=losses, pending=pending, wagered=wagered,
                    paid_out=paid, net=paid - settled_stake,
                    at_risk=wagered - settled_stake)

    def cumulative_net(self) -> list[tuple[int, float]]:
        total, out = 0.0, []
        for w in self.weeks:
            if w.net is None:
                break
            total += w.net
            out.append((w.week, total))
        return out

    # ---- per person
    def legs_for(self, person: str) -> list[Leg]:
        return [l for w in self.weeks for l in w.legs if l.person == person]

    def person_stats(self, person: str) -> dict:
        legs = self.legs_for(person)
        hits = sum(l.result == HIT for l in legs)
        misses = sum(l.result == MISS for l in legs)
        pushes = sum(l.result == PUSH for l in legs)
        pending = sum(l.result is None for l in legs)
        settled = [l for l in legs if l.settled]
        rate = hits / len(settled) if settled else None
        avg_implied = sum(l.implied for l in legs) / len(legs) if legs else None
        avg_odds = decimal_to_american(sum(l.decimal for l in legs) / len(legs)) if legs else None
        mvps = sum(1 for w in self.weeks if w.mvp and w.mvp.person == person)
        goats = sum(1 for w in self.weeks if w.goat and w.goat.person == person)
        anchors = sum(1 for w in self.weeks if w.status == "lost"
                      and [a.person for a in w.anchors] == [person])
        return dict(person=person, hits=hits, misses=misses, pushes=pushes,
                    pending=pending, rate=rate, avg_implied=avg_implied,
                    avg_odds=avg_odds, mvps=mvps, goats=goats, sole_anchors=anchors,
                    current_streak=current_streak(settled),
                    longest_hit_streak=longest_streak(settled, HIT))

    def leaderboard(self) -> list[dict]:
        rows = [self.person_stats(p) for p in self.members]
        return sorted(rows, key=lambda r: (-(r["rate"] if r["rate"] is not None else -1),
                                           -r["hits"], r["person"]))


# ------------------------------------------------------------------ streaks
def current_streak(settled: list[Leg]) -> str:
    """Return W3, L1 or a dash, over settled legs in week order."""
    if not settled:
        return "-"
    last = settled[-1].result
    n = 0
    for l in reversed(settled):
        if l.result != last:
            break
        n += 1
    return f"{'W' if last == HIT else 'L'}{n}"


def longest_streak(settled: list[Leg], kind: str) -> int:
    best = run = 0
    for l in settled:
        run = run + 1 if l.result == kind else 0
        best = max(best, run)
    return best
