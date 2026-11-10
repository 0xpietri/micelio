# Security policy

## Supported versions

Micelio is young. Only the latest release receives security fixes.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's
[private vulnerability reporting](https://github.com/0xpietri/micelio/security/advisories/new)
instead. You will get an answer within a week.

Helpful details: the version, how Micelio is deployed (Docker, `uvx`, behind which proxy),
and the steps to reproduce.

## Design notes

- Micelio only reads the vault. It never writes notes, so the vault can be mounted read-only.
- Anonymous visitors only ever see notes marked `public: true`.
- Secrets come from environment variables, never from `micelio.toml` or the repository.
- Note bodies are rendered from Markdown and sanitized; no inline scripts are served, so a
  strict Content Security Policy works.
