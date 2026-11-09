# Self-hosting on your own computer

Run the notes MCP server and Mycelium on your desktop or laptop (Linux, macOS or Windows) and
talk to your notes from any device, including your phone in voice mode.

**The trade-off:** it only works while the computer is on, awake and online. If you want
your notes reachable any time, use [a server](self-hosting-server.md) instead; the steps are
almost the same.

Time: about an hour the first time.

## What you need

- Docker: Docker Engine on Linux, Docker Desktop on macOS and Windows (WSL 2 backend).
- A free [Tailscale](https://tailscale.com) account, for a public HTTPS address without
  opening router ports or owning a domain. If you already have a domain on Cloudflare, a
  [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
  works the same way.
- An embedding backend for search by meaning, one of:
  - an OpenAI API key: a few cents for a whole vault, then near zero;
  - [Ollama](https://ollama.com) running `qwen3-embedding:0.6b`: free, but slow on a CPU
    beyond a few hundred notes.
- About 2 GB of free RAM.

## 1. Decide where the vault lives

The MCP server needs the vault on a Linux filesystem.

- **Linux:** use your Obsidian folder directly, for example `~/Obsidian`. Nothing else to do.
- **macOS and Windows:** your Obsidian folder is on APFS or NTFS, which the MCP server cannot
  write to safely through Docker. The stack keeps its own copy in a Docker volume, and
  [Syncthing](https://syncthing.net) keeps that copy and your Obsidian folder identical:
  1. Install Syncthing on the computer (on macOS, `brew install syncthing`; on Windows,
     SyncTrayzor or the official build) and share your Obsidian folder.
  2. The `syncthing` service in step 3 is the other end. Pair the two in their web interfaces
     (yours on `http://127.0.0.1:8384`, the container's on `http://127.0.0.1:8385`) and share
     the folder into `/vault` in the container.

  A note dictated from your phone is written into the volume by the MCP server and appears
  in Obsidian a few seconds later.

## 2. Get the MCP server

```sh
git clone --branch v1.2.0 https://github.com/maxkuminov/obsidian-mcp
cd obsidian-mcp
cp .env.example .env
cp postgres.env.example postgres.env
```

Pin a release tag, as above, and upgrade on purpose by reading its changelog.

Edit `.env`. The values that matter here:

```env
MCP_HOSTNAME=your-computer.your-tailnet.ts.net   # the Tailscale address from step 4
SECRET_KEY=...                                     # openssl rand -hex 32
OBSIDIAN_DB_PASSWORD=...                           # openssl rand -hex 32
VAULT_HOST_PATH=/home/you/Obsidian                 # Linux only; see step 3 for macOS/Windows

# Embeddings: pick one
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1024
# or
# EMBEDDING_PROVIDER=ollama
# OLLAMA_URL=http://host.docker.internal:11434
# EMBEDDING_MODEL=qwen3-embedding:0.6b
# EMBEDDING_DIMENSIONS=1024
```

Set `POSTGRES_PASSWORD` in `postgres.env` to another random value. The project's own
`.env.example` documents every other setting; the defaults are fine to start.

## 3. Start the stack

The project ships `docker-compose.proxy.yml` (PostgreSQL and the MCP server, no TLS). Add a
`compose.override.yml` next to it with a small Caddy that guards the admin pages, and, on
macOS and Windows, the Syncthing side:

```yaml
services:
  obsidian-mcp:
    ports: !reset []           # only Caddy talks to it
    # macOS/Windows: use the shared volume instead of VAULT_HOST_PATH
    # volumes: !override
    #   - vault:/obsidian

  gate:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:80"    # Tailscale Funnel points here
    volumes:
      - ./Caddyfile.gate:/etc/caddy/Caddyfile:ro
    networks: [mcp_internal]

  # macOS/Windows only
  # syncthing:
  #   image: syncthing/syncthing:1
  #   restart: unless-stopped
  #   ports:
  #     - "127.0.0.1:8385:8384"
  #     - "22000:22000"
  #   volumes:
  #     - vault:/vault
  #     - syncthing:/var/syncthing

# volumes:
#   vault:
#   syncthing:
```

`Caddyfile.gate`: the tunnel terminates HTTPS, so Caddy listens on plain HTTP and only adds a
password in front of the admin panel and the OAuth consent page:

```caddyfile
:80 {
	@admin path /admin* /api* /authorize
	handle @admin {
		basic_auth {
			# docker run --rm caddy:2 caddy hash-password --plaintext 'a long password'
			you $2a$14$REPLACE_WITH_THE_HASH
		}
		reverse_proxy obsidian-mcp:8000
	}
	handle {
		reverse_proxy obsidian-mcp:8000
	}
}
```

This matters: in single-user mode the MCP server has **no login of its own** on `/admin` and
`/authorize`. Without the gate, anyone who finds your address could approve themselves and
write to your notes.

Start it:

```sh
docker compose -f docker-compose.proxy.yml -f compose.override.yml up -d
docker compose -f docker-compose.proxy.yml logs -f obsidian-mcp   # wait for the first index
```

Set `TRUSTED_PROXY_IPS` in `.env` to the gate's address on the Docker network, as the
project's `DEPLOYMENT.md` explains, so rate limits see real client addresses.

## 4. Open it to the internet with Tailscale Funnel

Install Tailscale on the computer, sign in, then:

```sh
tailscale funnel --bg 8080
tailscale funnel status          # shows https://your-computer.your-tailnet.ts.net
```

Put that host name in `MCP_HOSTNAME` (step 2) and restart the MCP container if it changed.
OAuth only works when `MCP_HOSTNAME` matches the address clients use.

Check it from your phone's browser: `https://your-computer.your-tailnet.ts.net/health` should
answer `"status":"ok"`, and `/admin` should ask for the password.

## 5. Connect your assistant

- **Claude** (web, desktop and mobile): Settings → Connectors → Add custom connector, URL
  `https://your-computer.your-tailnet.ts.net/mcp`. You will see the consent page behind your
  gate password; choose **read + write**. The connector then shows up on your phone too,
  including voice mode.
- **ChatGPT**: add it as a connector in developer mode with the same URL.
- **Clients that take a header** (Claude Code, scripts): create an `omcp_` API key in
  `/admin` and send it as `Authorization: Bearer omcp_...`.

Try it: *"Read the vault guide, then create a note in notes/ about what we just discussed."*

## 6. Run Mycelium

Mycelium only reads, so it can use your normal Obsidian folder on any system:

```sh
uvx mycelium serve --vault ~/Obsidian        # http://127.0.0.1:8765
```

Keep it on `127.0.0.1`: it is for you on this computer. To show it to others, use a server
or, from v0.2, the static export of your public notes.

## 7. Keep the computer reachable

- Turn off sleep while plugged in (macOS: System Settings → Energy; Windows: Power &
  battery; Linux: your desktop's power settings).
- Make Docker and Tailscale start at login.
- Back up the vault folder. Git, Time Machine, File History or a copy on another machine all
  work; the vault is just files.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| The MCP container exits at start-up naming `openat2`, hard links or `renameat2` | The vault is on a macOS or Windows folder; use the volume + Syncthing setup |
| Claude says it cannot connect, or OAuth loops | `MCP_HOSTNAME` does not match the Funnel address |
| `/health` shows `"degraded"` | The embedding backend is unreachable; keyword search still works |
| Notes from the phone never reach Obsidian (macOS/Windows) | Syncthing is not paired or the folder is paused |
