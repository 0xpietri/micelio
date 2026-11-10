from __future__ import annotations

import pytest

from micelio.vault.parser import (
    WikiLink,
    extract_links,
    link_key,
    parse_note,
    slugify,
    split_frontmatter,
)


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Café conversations shape ideas", "cafe-conversations-shape-ideas"),
        ("A planet's tidal pull", "a-planet-s-tidal-pull"),
        ("  --Hello__World--  ", "hello-world"),
        ("日本語", "note"),
    ],
)
def test_slugify(text: str, slug: str) -> None:
    assert slugify(text) == slug


def test_link_key_is_case_insensitive_and_normalizes_unicode() -> None:
    nfd = "Café  Conversations"
    assert link_key(nfd) == link_key("café conversations")


def test_frontmatter_dates_become_strings() -> None:
    fm, body, error = split_frontmatter("---\ncreated: 2026-11-09\ntags: [a, b]\n---\nHello\n")
    assert fm == {"created": "2026-11-09", "tags": ["a", "b"]}
    assert body == "Hello\n"
    assert error is None


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("---\nkey: [unclosed\n---\nbody", "invalid frontmatter"),
        ("---\n- just\n- a list\n---\nbody", "not a key/value block"),
    ],
)
def test_broken_frontmatter_is_reported_not_raised(text: str, error: str) -> None:
    fm, body, message = split_frontmatter(text)
    assert fm == {}
    assert body == "body"
    assert message is not None
    assert error in message


def test_no_or_empty_frontmatter() -> None:
    assert split_frontmatter("# Title\n") == ({}, "# Title\n", None)
    assert split_frontmatter("---\n\n---\nx") == ({}, "x", None)


def test_extract_links_variants_and_code_is_ignored() -> None:
    body = (
        "See [[Alpha]], [[Beta#Part two|the second part]] and ![[diagram.png]].\n"
        "Inline `[[Not a link]]` is ignored.\n"
        "```\n[[Also not a link]]\n```\n"
        "[[ ]] is empty. [[Gamma|]] has an empty label.\n"
    )
    assert extract_links(body) == [
        WikiLink("Alpha"),
        WikiLink("Beta", heading="Part two", label="the second part"),
        WikiLink("diagram.png", embed=True),
        WikiLink("Gamma"),
    ]


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("---\ntitle: From frontmatter\n---\n# From heading\n", "From frontmatter"),
        ("---\ntitle: '  '\n---\n# From heading ##\n", "From heading"),
        ("```\n# not a heading\n```\nplain text\n", "fallback"),
    ],
)
def test_title_precedence(text: str, title: str) -> None:
    assert parse_note(text, fallback_title="fallback").title == title
