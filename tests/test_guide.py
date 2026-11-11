"""A project's guide (§3.4): structured and chronological orders, gaps and questions."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from micelio.app import create_app
from micelio.formatting import Dates
from micelio.guide import GuideBuilder
from micelio.vault import PublicView, VaultIndex
from micelio.vault.sections import drop_section, section

from .conftest import EXAMPLE_VAULT, VaultFactory, config_for
from .test_public import SiteFor, site_for  # noqa: F401 - the fixture

BAYES = "learning-bayesian-statistics"
DATES = Dates("en", "UTC")


def builder() -> GuideBuilder:
    return GuideBuilder(["Guide", "Guía"], DATES.created)


def client() -> TestClient:
    return TestClient(create_app(config_for(EXAMPLE_VAULT, auth="none"), local_only=True))


def test_sections_skip_code_and_match_without_accents() -> None:
    body = "# T\n\n## Guia\n### One\n- [[a]]\n```\n## Guía\n```\n- [[b]]\n## Next\n- [[c]]\n"
    lines = section(body, ["Guía"])
    assert lines is not None
    assert [chapter for chapter, _ in lines if "[[" in _] == ["One", "One"]
    assert "[[c]]" not in "".join(text for _, text in lines)
    assert drop_section(body, ["Guía"]) == "# T\n\n## Next\n- [[c]]\n"
    assert section("# T\n\n## Other\n[[a]]\n", ["Guide"]) is None


def test_structured_order_follows_the_guide_section(example_index: VaultIndex) -> None:
    guide = builder().build(example_index, example_index.notes[BAYES])
    assert guide.authored
    placed = [(s.slug, s.chapter) for s in guide.steps if s.placed]
    assert placed == [
        ("bayes-theorem-in-one-line", "The rule"),
        ("priors-are-beliefs-you-can-update", "The rule"),
        ("conditional-probability", "The rule"),
        ("likelihood-is-not-a-probability-of-the-hypothesis", "Building a model"),
        ("choosing-a-prior-is-a-modelling-decision", "Building a model"),
        ("who-was-thomas-bayes", "Building a model"),
    ]
    # Notes the index links outside the guide still show, last.
    rest = {s.slug for s in guide.steps if not s.placed}
    assert rest == {
        "effects-too-small-to-matter-can-still-be-real",
        "mcelreath-statistical-rethinking",
    }
    assert guide.gaps == 1
    assert [s.slug for s in guide.steps if s.is_gap] == ["conditional-probability"]


def test_chronological_order_sorts_by_creation(example_index: VaultIndex) -> None:
    guide = builder().build(example_index, example_index.notes[BAYES])
    days = [DATES.created(s.note) for s in guide.by_time if s.note]
    assert days == sorted(days)
    assert {s.slug for s in guide.by_time} == {s.slug for s in guide.steps}
    pager = guide.pager("priors-are-beliefs-you-can-update", "guide")
    assert pager.previous is not None
    assert pager.previous.slug == "bayes-theorem-in-one-line"
    assert pager.next is not None
    assert pager.next.slug == "conditional-probability"
    assert (pager.position, pager.total) == (2, len(guide.steps))


def test_without_a_guide_section_the_index_order_is_used(make_vault: VaultFactory) -> None:
    index = make_vault(
        {
            "projects/P.md": "---\ntype: project\n---\n# P\n\nFirst [[Zeta]], then [[Alpha]].\n",
            "notes/Alpha.md": "---\ncreated: 2026-01-01\n---\n# Alpha\n",
            "notes/Zeta.md": "---\ncreated: 2026-02-01\n---\n# Zeta\n",
        }
    )
    guide = builder().build(index, index.notes["p"])
    assert not guide.authored
    assert [s.slug for s in guide.steps] == ["zeta", "alpha"]
    assert [s.slug for s in guide.by_time] == ["alpha", "zeta"]


def test_gap_and_question_types_are_known(make_vault: VaultFactory) -> None:
    index = make_vault(
        {
            "notes/G.md": "---\ntype: gap\n---\n# G\n",
            "notes/Q.md": "---\ntype: question\n---\n# Q\n",
        }
    )
    assert index.notes["g"].type == "gap"
    assert index.notes["q"].type == "question"
    assert not [i for i in index.issues if i.kind == "unknown-type"]


def test_missing_notes_are_gaps_for_the_owner_only(make_vault: VaultFactory) -> None:
    files = {
        "projects/P.md": (
            "---\ntype: project\npublic: true\n---\n# P\n\n## Guide\n"
            "1. [[Seen]]\n2. [[Not written yet]]\n3. [[Secret xq]]\n"
        ),
        "notes/Seen.md": "---\npublic: true\n---\n# Seen\n",
        "notes/Secret xq.md": "# Secret xq\n",
    }
    index = make_vault(files)
    owner = builder().build(index, index.notes["p"])
    assert [(s.title, s.note is None) for s in owner.steps] == [
        ("Seen", False),
        ("Not written yet", True),
        ("Secret xq", False),
    ]
    public = PublicView(index)
    visitor = builder().build(public, public.notes["p"])
    assert [s.title for s in visitor.steps] == ["Seen"]


def test_project_page_shows_the_guide_beside_and_not_in_the_body() -> None:
    with client() as c:
        html = c.get(f"/projects/{BAYES}").text
    assert 'class="guide glass' in html
    assert "<h2>Guide</h2>" not in html
    assert html.count('data-guide-list="guide"') == 1
    assert 'data-guide-list="time" hidden' in html
    assert 'data-kind="gap"' in html
    assert 'data-kind="question"' in html
    assert '<script type="module" src="/static/js/guide.js"></script>' in html
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert not re.search(r"<style\b", html)


def test_note_page_has_the_guide_and_a_pager() -> None:
    with client() as c:
        html = c.get("/notes/conditional-probability").text
        question = c.get("/notes/who-was-thomas-bayes").text
    assert 'aria-current="page"' in html
    assert 'class="type-banner gap"' in html
    assert 'rel="prev"' in html
    assert 'rel="next"' in html
    assert 'class="type-banner question"' in question


def test_a_note_in_two_projects_picks_its_guide() -> None:
    priors = "/notes/priors-are-beliefs-you-can-update"
    with client() as c:
        first = c.get(priors).text
        chosen = c.get(f"{priors}?guide={BAYES}").text
        unknown = c.get(f"{priors}?guide=no-such-project").text
    assert "Also the guide of:" in first
    assert 'href="?guide=learning-bayesian-statistics"' in first
    assert 'href="?guide=free-will-in-a-determined-world"' in chosen
    assert unknown.count('href="?guide=learning-bayesian-statistics"') == 1
    # Links inside the guide keep it for notes that belong to more than one project.
    assert f'href="/notes/priors-are-beliefs-you-can-update?guide={BAYES}"' in chosen


def test_visitors_see_no_private_or_missing_step(site_for: SiteFor) -> None:  # noqa: F811
    site = site_for(
        {
            "projects/Open.md": (
                "---\ntype: project\npublic: true\n---\n# Open\n\n## Guide\n"
                "1. [[Seen]]\n2. [[Nowhere xq]]\n3. [[Hidden xq]]\n"
            ),
            "notes/Seen.md": "---\npublic: true\n---\n# Seen\n",
            "notes/Hidden xq.md": "# Hidden xq\n",
        }
    )
    for path in ("/projects/open", "/notes/seen"):
        body = site.client.get(path).text
        assert 'class="guide glass' in body
        assert "xq" not in body.lower(), path
    site.sign_in()
    owner = site.client.get("/projects/open").text
    assert "Nowhere xq" in owner
    assert "Hidden xq" in owner
