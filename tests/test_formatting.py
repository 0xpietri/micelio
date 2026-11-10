from __future__ import annotations

import os
from datetime import date

from micelio.formatting import Dates
from micelio.vault import VaultIndex

from .conftest import VaultFactory


def test_dates_follow_language() -> None:
    assert Dates("en", "UTC").show(date(2026, 11, 9)) == "Nov 9, 2026"
    assert Dates("es", "UTC").show(date(2026, 11, 9)) == "9 nov 2026"


def test_created_and_updated(make_vault: VaultFactory) -> None:
    vault: VaultIndex = make_vault(
        {
            "journal/2026-10-05 Talk.md": "",
            "notes/A.md": "---\ncreated: 2026-01-02\nupdated: 2026-03-04T10:00\n---\n",
            "notes/B.md": "---\ncreated: someday\n---\n",
        }
    )
    b_path = vault.root / "notes" / "B.md"
    os.utime(b_path, (1_800_000_000, 1_800_000_000))  # 2027-01-15 08:00 UTC
    vault.refresh(force=True)
    dates = Dates("en", "Pacific/Kiritimati")  # UTC+14: already the next day
    assert dates.created(vault.notes["2026-10-05-talk"]) == date(2026, 10, 5)
    assert dates.created(vault.notes["a"]) == date(2026, 1, 2)
    assert dates.updated(vault.notes["a"]) == date(2026, 3, 4)
    assert dates.created(vault.notes["b"]) == date(2027, 1, 15)
    assert Dates("en", "Pacific/Pago_Pago").modified(vault.notes["b"]) == date(2027, 1, 14)
