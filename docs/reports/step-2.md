# Step 2 report: sign-in

Date: 2026-11-09

## Done

- **Secrets from the environment only**: `MICELIO_PASSWORD_HASH` (argon2id),
  `MICELIO_TOTP_SECRET` (base32), `MICELIO_SESSION_KEY` (32+ characters). Malformed or
  partial secrets stop the server with a message naming each one and the command that makes it.
- **When sign-in is on** (`auth/settings.py`): `auth.mode = "none"` turns it off; listening on
  loopback with no secrets turns it off (spec §10, the `uvx` case); anywhere else all three
  secrets are required. `micelio serve` says on start-up when sign-in is off and why.
- **Sign-in** (`auth/web.py`): one form with password and 6-digit code; RFC 6238 TOTP written
  with the standard library (tested against the RFC vectors), one step of drift, a code or
  any earlier step can never be reused. Failures never say which half was wrong.
- **Sessions** (`auth/store.py`): random tokens, only their SHA-256 in SQLite under
  `[data].dir`, 12 h, `HttpOnly`, `SameSite=Strict`, `Secure` except on plain-HTTP localhost
  (where Safari would drop the cookie). Sign-out deletes the row; `micelio user sign-out-all`
  deletes them all.
- **Lockout**: 5 failures per address in 15 minutes return 429 until the window passes;
  stored in SQLite, so a restart does not reset it. A success clears the address.
- **CSRF**: sign-in uses a nonce cookie plus an HMAC form token; sign-out an HMAC of the
  session. `next` only accepts same-site paths.
- **Every other path** redirects to `/login?next=…` (GET) or answers 401; `/healthz`,
  `/login` and `/static/` stay open. Public notes (step 6) will refine this per route.
- **Security headers** on every response: CSP `default-src 'self'` with no inline code,
  `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: same-origin`.
- **CLI**: `micelio user set-password | totp | session-key | sign-out-all`. Output is ready to
  paste into `.env`, single-quoted so the `$` in argon2 hashes survives Docker Compose. `totp`
  draws a QR code and insists on a correct code before printing the secret; on a terminal that
  cannot draw it, it prints the `otpauth://` link instead.
- **First templates and i18n**: `base.html`, `login.html`, a placeholder `home.html`;
  `locales/en.toml` with a `t()` helper and a test that every locale has exactly the English
  keys. Step 3 adds Spanish and Babel.
- New config: `[auth] session_hours, max_failures, lockout_minutes`, `[data] dir`
  (`MICELIO_DATA`). `serve --forwarded-allow-ips` for proxies that are not on 127.0.0.1.

Tests: 137, coverage 99 %. Checked in a real browser too: sign-in with a live TOTP code, the
home page, sign-out.

## Spec changes

- §5 now says how the loopback rule works, that partial secrets are an error, that the CLI
  prints `.env` lines, and how sign-in and sign-out are protected against CSRF.

## Open points

- The lockout counts by client address. Behind Caddy on the same host this is the real
  visitor; in Docker, pass `--forwarded-allow-ips` with the proxy's address or every
  visitor shares one counter (safe, but a stranger could lock you out for 15 minutes).
