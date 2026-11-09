# Rules for AI agents working in this repository

These rules apply to any coding assistant (Claude, Codex, Copilot, Gemini, local models).

## Source of truth

- The specification is `docs/spec/MYCELIUM_SPEC_v0.1.md`. Read it before any change.
- Implement only the step you were asked for (spec §14). Each step ends with tests, a short
  report in `docs/reports/` and a stop for review.
- If the spec is ambiguous or contradicts itself, stop on that point, explain it and propose
  options instead of guessing.

## Boundaries

- Mycelium **reads** the vault. It never creates, edits, moves or deletes notes, and never
  runs Git in the vault.
- Anonymous visitors see only notes with `public: true`. Any new page or endpoint needs a test
  proving no private title, path or tag leaks to an anonymous request.
- Secrets come only from environment variables. Commit `.env.example` with placeholders only.
- No inline `<script>` or `<style>` blocks; the Content Security Policy only allows files
  under `/static` (inline `style=""` attributes are allowed for computed sizes and colors).
- Personal values (names, categories, colors, folders) belong in `mycelium.toml`, never in code.

## Engineering

- Python 3.12+, FastAPI + Jinja templates, plain CSS/JS with no build step, SQLite for the
  site's own state, `uv` with a lockfile, `pytest`, `ruff`, `mypy --strict`.
- Must work on Linux, macOS and Windows: use `pathlib`, UTF-8 everywhere, no shell-outs.
- Every behaviour change comes with tests; the sample vault in `examples/vault` is the shared
  fixture.
- Code, comments, docs, commit messages and the interface are in English. Interface strings
  live in `locales/*.toml`.
- Before pushing: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`.
