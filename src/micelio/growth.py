"""How a project grows (§7c): its notes added and edited week by week, and a stage.

Shown as a small card on the project's scene: twelve bars, one per week (notes created,
notes edited and journal entries that mention the project), and a stage named after the
mycelium, from the last thirty days: new notes count twice, edits and journal entries once.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from micelio.vault.index import Note

WEEKS = 12
RECENT_DAYS = 30
# The smallest score of each stage; below the first is dormant.
STAGES: tuple[tuple[int, str], ...] = ((10, "fruiting"), (4, "growing"), (1, "germinating"))


@dataclass(frozen=True)
class Growth:
    weeks: tuple[int, ...]  # oldest first; the last one is this week
    score: int
    stage: str
    added: int  # notes created in the last thirty days

    @property
    def peak(self) -> int:
        return max(self.weeks) if self.weeks else 0

    def height(self, count: int) -> int:
        """A bar's height in percent of the tallest; an empty week keeps a sliver."""
        return max(6, round(100 * count / self.peak)) if self.peak and count else 6


def stage_of(score: int) -> str:
    for least, name in STAGES:
        if score >= least:
            return name
    return "dormant"


def growth(
    notes: Iterable[Note],
    journals: Iterable[Note],
    created: Callable[[Note], date],
    updated: Callable[[Note], date],
    today: date,
) -> Growth:
    """``notes`` are the project and its notes; ``journals`` the entries that touch them."""
    weeks = [0] * WEEKS
    start = today - timedelta(days=today.weekday() + 7 * (WEEKS - 1))  # a Monday
    recent = today - timedelta(days=RECENT_DAYS)
    score = added = 0

    def count(day: date, weight: int) -> None:
        nonlocal score
        if start <= day <= today:
            weeks[(day - start).days // 7] += 1
        if recent < day <= today:
            score += weight

    for note in notes:
        born, touched = created(note), updated(note)
        count(born, 2)
        if recent < born <= today:
            added += 1
        if touched > born:
            count(touched, 1)
    for entry in journals:
        count(created(entry), 1)
    return Growth(tuple(weeks), score, stage_of(score), added)
