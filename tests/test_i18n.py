from __future__ import annotations

from mycelium.i18n import available_languages, load_strings, translator


def test_english_is_available() -> None:
    assert "en" in available_languages()


def test_every_locale_has_exactly_the_english_keys() -> None:
    reference = set(load_strings("en"))
    for language in available_languages():
        keys = set(load_strings(language))
        assert keys == reference, (
            f"{language}: missing {reference - keys}, extra {keys - reference}"
        )


def test_placeholders_and_fallbacks() -> None:
    t = translator("en")
    assert t("login.locked", minutes=15) == "Too many attempts. Try again in 15 minutes."
    assert t("no.such.key") == "no.such.key"
    assert translator("xx")("login.title") == "Sign in"
