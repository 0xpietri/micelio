"""Projects the owner shared from the site (§9): the switch on a project's page.

Sharing a project lets anonymous visitors read it and the notes it links to, as if each
said ``public: true``. The choice lives in the data folder (``site.sqlite3``, key
``shared_projects``), never in the vault, which Micelio only reads (§2). Turning it off
hides them again at once; a note whose own frontmatter says ``public: true`` stays public.
"""

from __future__ import annotations

from micelio.appearance import AppearanceStore

_KEY = "shared_projects"


class SharedProjects:
    """The slugs of the projects shared from the site, next to the Appearance choices."""

    def __init__(self, store: AppearanceStore) -> None:
        self.store = store

    def all(self) -> frozenset[str]:
        raw = self.store.read_setting(_KEY)
        if not isinstance(raw, list):
            return frozenset()
        return frozenset(slug for slug in raw if isinstance(slug, str))

    def is_shared(self, slug: str) -> bool:
        return slug in self.all()

    def set(self, slug: str, shared: bool) -> None:
        slugs = set(self.all())
        if shared:
            slugs.add(slug)
        else:
            slugs.discard(slug)
        self.store.write_setting(_KEY, sorted(slugs))
