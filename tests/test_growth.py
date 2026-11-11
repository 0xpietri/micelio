"""How a project grows (§7c): twelve weeks of notes and a stage on its scene."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any, cast

from fastapi.testclient import TestClient

from micelio.growth import Growth, growth, stage_of
from micelio.vault.index import Note

from .test_landing import client as client  # the fixture

TODAY = date(2026, 11, 11)  # a Wednesday


def note(born: date, touched: date | None = None) -> Note:
    return cast(Note, SimpleNamespace(born=born, touched=touched or born))


def run(notes: list[Note], journals: list[Note] | None = None) -> Growth:
    def created(n: Any) -> date:
        return cast(date, n.born)

    def updated(n: Any) -> date:
        return cast(date, n.touched)

    return growth(notes, journals or [], created, updated, TODAY)


def test_stages() -> None:
    assert [stage_of(s) for s in (0, 1, 3, 4, 9, 10)] == [
        "dormant",
        "germinating",
        "germinating",
        "growing",
        "growing",
        "fruiting",
    ]


def test_weeks_score_and_new_notes() -> None:
    days = timedelta
    result = run(
        [
            note(TODAY - days(2)),  # new this week: 2
            note(TODAY - days(10), TODAY - days(1)),  # new (2) and edited (1)
            note(TODAY - days(200), TODAY - days(3)),  # old, edited this week: 1
            note(TODAY - days(300)),  # nothing recent
        ],
        [note(TODAY - days(20))],  # a journal entry: 1
    )
    assert len(result.weeks) == 12
    assert result.weeks[-1] == 2  # since Monday: one new note, one edit (Sunday is last week)
    assert sum(result.weeks) == 5
    assert result.score == 7  # 2 + (2 + 1) + 1 + 1
    assert result.added == 2
    assert result.stage == "growing"
    assert result.height(result.peak) == 100
    assert result.height(0) == 6


def test_a_quiet_project_is_dormant() -> None:
    result = run([note(TODAY - timedelta(days=400))])
    assert result.stage == "dormant"
    assert result.weeks == (0,) * 12
    assert result.height(0) == 6


def test_the_scene_shows_the_card_not_the_old_eyebrow(client: TestClient) -> None:
    html = client.get("/projects/cities-as-living-organisms").text
    assert 'class="growth glass stage-' in html
    assert html.count("<rect ") >= 12
    assert 'class="eyebrow"' not in html.split('class="project-page"')[0]


def test_growth_card_stands_on_the_soil() -> None:
    from pathlib import Path

    static = Path(__file__).resolve().parents[1] / "src" / "micelio" / "static"
    assert "--soil-y" in (static / "js" / "graph.js").read_text("utf-8")
    assert ".hero-scene.has-soil .growth" in (static / "css" / "graph.css").read_text("utf-8")


def test_threads_show_what_they_join() -> None:
    from pathlib import Path

    script = (Path(__file__).resolve().parents[1] / "src/micelio/static/js/graph.js").read_text(
        "utf-8"
    )
    for kind in ("member", "journal", "source", "link", "ghost"):
        assert f"{kind}: {{ color" in script
    assert "k-${t.kind}" in script
