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
    placed = [(s.number, s.slug or s.title, s.depth) for s in guide.steps if s.placed]
    assert placed == [
        ("1", "The rule", 0),
        ("1.1", "bayes-theorem-in-one-line", 1),
        ("1.2", "conditional-probability", 1),
        ("1.3", "priors-are-beliefs-you-can-update", 1),
        ("2", "Building a model", 0),
        ("2.1", "likelihood-is-not-a-probability-of-the-hypothesis", 1),
        ("2.2", "choosing-a-prior-is-a-modelling-decision", 1),
        ("2.2.1", "who-was-thomas-bayes", 2),
    ]
    assert guide.number_of("who-was-thomas-bayes") == "2.2.1"
    # Notes the index links outside the guide still show, last.
    rest = {s.slug for s in guide.steps if not s.placed}
    assert rest == {
        "effects-too-small-to-matter-can-still-be-real",
        "mcelreath-statistical-rethinking",
    }
    assert guide.gaps == 1
    assert [s.slug for s in guide.steps if s.is_gap] == ["conditional-probability"]
    kinds = {s.slug: s.kind for s in guide.steps if s.slug}
    assert kinds["who-was-thomas-bayes"] == "question"


def test_numbers_follow_the_shape_not_the_text(make_vault: VaultFactory) -> None:
    # Headings and list items both make sections; numbers written in the text are ignored,
    # so inserting a line renumbers everything after it.
    index = make_vault(
        {
            "projects/P.md": (
                "---\ntype: project\n---\n# P\n\n## Guía\n### Basics\n"
                "1. [[A]]\n1. [[B]] · [[C]]\n    - [[D]]\n#### Deeper\n- [[E]]\n"
                "### Empty stretch\n### Last\n7. Sub part\n   9. [[F]]\n\n## Next\n[[G]]\n"
            ),
            **{f"notes/{n}.md": f"# {n}\n" for n in "ABCDEFG"},
        }
    )
    guide = builder().build(index, index.notes["p"])
    assert [(s.number, s.slug or s.title) for s in guide.steps if s.placed] == [
        ("1", "Basics"),
        ("1.1", "a"),
        ("1.2", "b"),
        ("1.2.1", "d"),
        ("1.3", "c"),
        ("1.4", "Deeper"),
        ("1.4.1", "e"),
        ("2", "Last"),
        ("2.1", "Sub part"),
        ("2.1.1", "f"),
    ]
    assert [s.slug for s in guide.steps if not s.placed] == ["g"]


def test_chronological_order_sorts_by_creation(example_index: VaultIndex) -> None:
    guide = builder().build(example_index, example_index.notes[BAYES])
    days = [DATES.created(s.note) for s in guide.by_time if s.note]
    assert days == sorted(days)
    assert {s.slug for s in guide.by_time} == {s.slug for s in guide.steps if s.slug}
    assert [s.number for s in guide.by_time] == [str(i + 1) for i in range(len(guide.by_time))]
    pager = guide.pager("conditional-probability", "guide")
    assert pager.previous is not None
    assert pager.previous.slug == "bayes-theorem-in-one-line"
    assert pager.next is not None
    assert pager.next.slug == "priors-are-beliefs-you-can-update"
    assert (pager.position, pager.total) == (2, len(guide.by_time))


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


def test_the_guide_leads_back_to_its_project_home() -> None:
    home = f'<a href="/projects/{BAYES}">Project home</a>'
    with client() as c:
        note = c.get("/notes/conditional-probability").text
        project = c.get(f"/projects/{BAYES}").text
        chosen = c.get(f"/notes/priors-are-beliefs-you-can-update?guide={BAYES}").text
    assert home in note
    assert home in chosen
    # On the project's own page the link marks where the reader is.
    assert f'<a href="/projects/{BAYES}" aria-current="page">Project home</a>' in project


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


def test_conversations_open_the_guide() -> None:
    with client() as c:
        html = c.get("/projects/do-planets-at-birth-leave-a-trace").text
    assert 'class="guide-talks"' in html
    assert "Conversations (1)" in html
    assert 'href="/notes/2026-11-09-planets"' in html


def test_order_is_a_dropdown_and_the_pager_follows_the_kinds() -> None:
    with client() as c:
        html = c.get("/notes/conditional-probability").text
    assert "<select data-guide-order>" in html
    assert 'data-position="{position} of {total}"' in html
    assert 'data-depth="1"' in html
    assert '<span class="guide-number">1.2</span>' in html


def test_authors_read_like_names() -> None:
    from micelio.formatting import author_name

    assert author_name("claude-opus-5-5") == "Claude Opus 5.5"
    assert author_name("claude-sonnet-5") == "Claude Sonnet 5"
    assert author_name("marcos") == "marcos"
    assert author_name(None) == ""
    with client() as c:
        html = c.get("/notes/who-was-thomas-bayes").text
    assert "Claude Sonnet 5.5" in html
    assert '<span class="author-chip">marcos</span>' in html


def test_tags_open_the_graph() -> None:
    with client() as c:
        html = c.get("/notes/who-was-thomas-bayes").text
        nodes = c.get("/api/graph").json()["nodes"]
    assert '<a class="tag" href="/explore?tag=history"' in html
    assert next(n for n in nodes if n["id"] == "who-was-thomas-bayes")["tags"] == [
        "statistics",
        "history",
    ]
