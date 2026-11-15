"""The owner's Share switch on a project's page (§9): a shared project and the notes it
links to are readable without signing in. The choice is kept in the data folder."""

from __future__ import annotations

import re
from http.cookiejar import Cookie
from pathlib import Path

from micelio.appearance import AppearanceStore
from micelio.sharing import SharedProjects

from .test_auth_web import Site
from .test_landing import make_config
from .test_public import MARK, VAULT, SiteFor, crawl
from .test_public import site_for as site_for  # the fixture

PRIVATE = "vault-xq-plan"  # links to Shared root, Seed idea and Lonely xq
PUBLIC = "open-garden"  # public: true in its own frontmatter


def share_form(site: Site, slug: str = PRIVATE) -> dict[str, str]:
    page = site.client.get(f"/projects/{slug}").text
    form = re.search(r'<form class="share-switch[^"]*".*?</form>', page, re.S)
    assert form, "the owner's project page carries the Share switch"
    fields = dict(re.findall(r'name="(\w+)" value="([^"]*)"', form.group(0)))
    return fields


def toggle(site: Site, slug: str = PRIVATE) -> None:
    answer = site.client.post(
        f"/projects/{slug}/share", data=share_form(site, slug), follow_redirects=False
    )
    assert answer.status_code == 303
    assert answer.headers["location"] == f"/projects/{slug}"


def as_visitor(site: Site) -> list[Cookie]:
    """Drop the owner's cookies (and hand them back), to look as a visitor."""
    cookies = list(site.client.cookies.jar)
    site.client.cookies.clear()
    return cookies


def back_as_owner(site: Site, cookies: list[Cookie]) -> None:
    for cookie in cookies:
        site.client.cookies.jar.set_cookie(cookie)


def test_shared_projects_are_kept_in_the_data_folder(tmp_path: Path) -> None:
    store = AppearanceStore(make_config(tmp_path))
    shared = SharedProjects(store)
    assert shared.all() == frozenset()
    shared.set("a", True)
    shared.set("b", True)
    shared.set("a", False)
    shared.set("c", False)
    assert shared.all() == {"b"}
    assert shared.is_shared("b")
    assert not shared.is_shared("a")
    store.write_setting("shared_projects", ["d", 3, None])
    assert shared.all() == {"d"}
    store.write_setting("shared_projects", {"oops": True})
    assert shared.all() == frozenset()
    store.close()


def test_sharing_a_project_opens_it_and_its_notes_to_visitors(site_for: SiteFor) -> None:
    site = site_for(VAULT)
    assert site.client.get(f"/projects/{PRIVATE}").status_code == 404
    assert site.client.get("/notes/lonely-xq").status_code == 404
    site.sign_in()

    fields = share_form(site)
    assert fields["shared"] == "on", "a private project offers to share"
    assert 'aria-checked="false"' in site.client.get(f"/projects/{PRIVATE}").text
    toggle(site)
    page = site.client.get(f"/projects/{PRIVATE}").text
    assert 'aria-checked="true"' in page
    assert share_form(site)["shared"] == "", "a shared project offers to make it private"
    assert "badge shared" in site.client.get("/projects").text

    owner = as_visitor(site)
    page = site.client.get(f"/projects/{PRIVATE}")
    assert page.status_code == 200
    assert "Secret xq plan" in page.text
    assert "Lonely xq" in page.text
    assert "<form" not in page.text, "visitors only look"
    assert "share-switch" in page.text, "and they see the mushroom"
    assert 'class="growth' in page.text, "and the growth card"
    assert "Spores in the air" in page.text
    assert "title=" not in page.text.split("share-switch", 1)[1].split("</div>", 1)[0]
    assert "Spores in the air" in page.text
    assert "badge shared" not in site.client.get("/projects").text
    assert site.client.get("/notes/lonely-xq").status_code == 200
    nodes = {n["id"] for n in site.client.get("/api/graph").json()["nodes"]}
    assert {PRIVATE, "lonely-xq"} <= nodes

    # Only the project and what it links to: the rest stays private.
    pages = crawl(site.client)
    shown = {"secret xq plan", "lonely xq", "vault-xq-plan", "lonely-xq", "tagxq"}
    for path, body in pages.items():
        text = body.lower()
        for name in shown:
            text = text.replace(name, "")
        assert MARK not in text, path
    assert site.client.get("/notes/private-xq").status_code == 404

    back_as_owner(site, owner)
    toggle(site)
    as_visitor(site)
    assert site.client.get(f"/projects/{PRIVATE}").status_code == 404
    assert site.client.get("/notes/lonely-xq").status_code == 404
    for path, body in crawl(site.client).items():
        assert MARK not in body.lower(), path


def test_a_project_public_in_its_note_shows_as_shared(site_for: SiteFor) -> None:
    site = site_for(VAULT)
    site.sign_in()
    page = site.client.get(f"/projects/{PUBLIC}").text
    form = re.search(r'<form class="share-switch[^"]*".*?</form>', page, re.S)
    assert form
    assert "<button" not in form.group(0), "set in the vault, not here"
    assert "public: true" in form.group(0)
    as_visitor(site)
    page = site.client.get(f"/projects/{PUBLIC}").text
    assert re.search(r'class="share-switch[^"]* on"', page)
    assert "<form" not in page


def test_the_switch_sits_on_the_title_line(site_for: SiteFor) -> None:
    # One line: the project's title, then the switch's drawing and its words.
    site = site_for(VAULT)
    site.sign_in()
    page = site.client.get(f"/projects/{PRIVATE}").text
    line = re.search(r'<div class="title-line">(.*?)</div>\s*</div>', page, re.S)
    assert line, "the title has its own line in the scene's heading"
    assert "<h1>" in line.group(1)
    assert "share-switch" in line.group(1)
    cards = page.split('<div class="scene-cards">', 1)[1].split("</section>", 1)[0]
    assert "share-switch" not in cards
    # Shared or not, the words keep one color: only the drawing and the words change.
    static = Path(__file__).parents[1] / "src" / "micelio" / "static"
    css = (static / "css" / "graph.css").read_text("utf-8")
    assert ".share-switch.on .share-caption" not in css


def test_only_the_owner_can_share(site_for: SiteFor) -> None:
    site = site_for(VAULT)
    anonymous = site.client.post(f"/projects/{PRIVATE}/share", data={"shared": "on"})
    assert anonymous.status_code == 401
    site.sign_in()
    forged = site.client.post(f"/projects/{PRIVATE}/share", data={"csrf": "nope", "shared": "on"})
    assert forged.status_code == 403
    fields = share_form(site)
    assert site.client.post("/projects/seed-idea/share", data=fields).status_code == 404
    assert site.client.post("/projects/nothing/share", data=fields).status_code == 404
    as_visitor(site)
    assert site.client.get(f"/projects/{PRIVATE}").status_code == 404


def test_the_share_card_shows_the_scene_style(site_for: SiteFor) -> None:
    site = site_for(VAULT)
    site.sign_in()
    page = site.client.get(f"/projects/{PRIVATE}").text
    # Pictures by default, in the scene's style: only the mycelium while private.
    assert "/static/img/share/blacklight/underground.webp" in page
    toggle(site)
    page = site.client.get(f"/projects/{PRIVATE}").text
    assert "/static/img/share/blacklight/spores.webp" in page
    # Painted in the palette's colors: the drawn card.
    look = site.client.get("/appearance").text.split('id="look-form"', 1)[1]
    token = re.search(r'name="csrf" value="([^"]+)"', look)
    assert token
    data = {"csrf": token.group(1), "background": "neon-sun", "mushrooms": "drawn", "soil": "52"}
    assert site.client.post("/appearance", data=data, follow_redirects=False).status_code == 303
    page = site.client.get(f"/projects/{PRIVATE}").text
    assert "/static/img/share/" not in page
    assert 'class="share-shroom"' in page
