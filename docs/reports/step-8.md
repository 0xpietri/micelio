# Step 8: release v0.1.0

## What was asked

Spec §14 step 8: Docker image, compose example, README with GIF and diagram, CHANGELOG,
tag; with the packaging rules of §10 and §11 (image on GHCR, amd64 on `main`, amd64 + arm64
on tags, a PyPI package for personal computers, GitHub releases).

During the step marcos renamed the project from Mycelium to **Micelio** everywhere
(decision in §15): `mycelium` was taken on PyPI and the Spanish name sits better with him.

## What was built

- **Rename.** Package `src/micelio`, command `micelio`, environment variables `MICELIO_*`,
  config file `micelio.toml`, image `ghcr.io/0xpietri/micelio`, PyPI package `micelio`,
  spec `docs/spec/MICELIO_SPEC_v0.1.md`, site `micelio.pietri.dev`. The English word
  *mycelium* stays where the text describes the drawing ("graphs drawn as mycelium").
  The English landing title is now "{owner}'s Micelio"; Spanish stays "El micelio de {owner}".
- **Dockerfile**: two stages. `uv sync --locked --no-dev` builds `/app/.venv` (dependencies
  in their own layer); the runtime stage is `python:3.12-slim` with the venv only, user
  `micelio` (uid 10001), `/vault` and `/data`, a health check on `/healthz`, entrypoint
  `micelio`, command `serve`. Works with `--read-only` plus a `/tmp` tmpfs (uploads spool
  there). Image: 63 MB compressed; the demo used 48 MB of RAM.
- **`compose.example.yml`**: `docker compose -f compose.example.yml up` runs the sample vault
  on `127.0.0.1:8765`, read-only root, dropped capabilities, `no-new-privileges`. It mounts
  `examples/demo.toml`, which only sets `auth.mode = "none"` (said plainly in both files).
- **`micelio serve`** reads `MICELIO_HOST`, `MICELIO_PORT` and
  `MICELIO_FORWARDED_ALLOW_IPS` as defaults (flags still win), so the image sets
  `0.0.0.0:8765` once and a proxy can be trusted without changing the command.
- **Workflows**: `image.yml` builds `linux/amd64` on `main` (tags `edge`, `sha-…`), and
  `linux/amd64,linux/arm64` on `v*` tags (`0.1.0`, `0.1`, `latest`; no `0` while in 0.x).
  It first builds for amd64 and smoke-tests the container (healthz, `/`, `/explore`) before
  pushing. A manual run builds both architectures without pushing. `release.yml` checks
  that the tag equals the package version and that the CHANGELOG has its section, runs the
  tests, builds wheel and sdist, publishes to PyPI by trusted publishing and creates the
  GitHub release with the CHANGELOG section as notes.
- **Package**: version `0.1.0`; the sdist carries the source, tests and sample vault, not
  the design files (480 KB instead of 2.4 MB).
- **README**: GIF of the sample vault (landing, then `/explore` with zoom), a Mermaid
  architecture diagram (renders on GitHub, no image to keep in sync), the three ways to run
  it, security notes and the roadmap after v0.1. Guides updated to the real image and
  package.
- **CHANGELOG**: `[0.1.0] - 2026-11-10`, grouped by area, with compare links.
- Dependabot also watches the Dockerfile.

## Tests

- `tests/test_release.py`: installed version equals `pyproject.toml`; the command entry
  point; CHANGELOG has a dated section and link for the version; the demo config turns
  sign-in off; the compose example's bind mounts exist and keep the vault read-only; the
  Dockerfile runs as `micelio` with the expected environment.
- `tests/test_cli.py`: `serve` defaults from the environment, flags win, a bad port exits 2.
- Checked by hand: image built and run with `--read-only`; compose demo healthy; an
  uploaded background lands in `/data/backgrounds`; without secrets on `0.0.0.0` the
  container refuses to start with the usual message.
- ruff, ruff format, mypy --strict: clean. pytest: 306 passed, coverage 98.3 %.

## Not done here (needs marcos)

1. **Rename the GitHub repository** to `micelio` (Settings → General). GitHub redirects the
   old URLs; the code already points at `0xpietri/micelio`.
2. **PyPI trusted publisher**: on pypi.org, *Publishing → Add a pending publisher*: project
   `micelio`, owner `0xpietri`, repository `micelio`, workflow `release.yml`, environment
   `pypi`. Without it the PyPI job fails; the image and the GitHub release still go out.
3. **The tag** `v0.1.0` on `main` after merging, which publishes everything.
4. The arm64 image was not built here (no emulator in this sandbox); the manual run of
   `image.yml` tries it without publishing.
5. After the first push to GHCR, make the package public (GitHub → Packages → micelio →
   Package settings → visibility) so `docker pull` works without signing in.
6. The deployment on factory (`micelio.pietri.dev`) is tracked outside this repository.
