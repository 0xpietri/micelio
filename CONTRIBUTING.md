# Contributing

Thanks for wanting to help. Issues and pull requests are welcome.

## Set up

You need [uv](https://docs.astral.sh/uv/). It installs the right Python for you.

```sh
git clone https://github.com/0xpietri/mycelium
cd mycelium
uv sync
uv run mycelium serve --vault examples/vault   # http://127.0.0.1:8765
```

## Before you open a pull request

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov
```

CI runs the same commands on Linux, macOS and Windows.

## Guidelines

- Every change in behaviour comes with a test. The sample vault in `examples/vault` is the
  shared fixture; extend it when a new case needs a real note.
- The specification lives in `docs/spec/`. Larger changes start as an issue that points at the
  section they touch.
- Keep the front end free of build steps: plain CSS and JavaScript files, no inline `<script>`
  or `<style>` blocks.
- Code, comments, docs and commit messages are in English. Interface strings go in
  `locales/*.toml`, never in templates.
- One topic per pull request, with a short description of what and why.
