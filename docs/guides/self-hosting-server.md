# Self-hosting on a server

Run the notes MCP server and Mycelium on a small Linux server, so you can dictate notes from
your phone at any time and read them on your own website, with your computers switched off.

Time: an afternoon the first time.

## Which hosting works

You need a **VPS**: a small Linux virtual machine where you have root and can run Docker.
Any provider works (Hetzner, DigitalOcean, OVH, Scaleway, Oracle's free tier, a Raspberry Pi
at home with a tunnel). Aim for:

- Ubuntu 24.04 or Debian 12 (Linux kernel 5.8 or newer);
- 2 GB of RAM (4 GB if you run Ollama on the same machine), 20 GB of disk;
- a domain name whose DNS you control.

**Shared web hosting does not work** (cPanel and similar plans that host PHP sites): it cannot
run Docker or long-lived processes. Platform services (Fly, Railway, Render) are possible in
theory but awkward here, because the vault must live on a persistent Linux disk that you
also sync to your devices.

## 1. Prepare the server

```sh
# as root, once
apt update && apt upgrade -y
adduser you && usermod -aG sudo you
# install Docker Engine: https://docs.docker.com/engine/install/
usermod -aG docker you
ufw allow OpenSSH && ufw allow 80,443/tcp && ufw allow 22000 && ufw enable
```

Use SSH keys and turn off password login. Enable unattended security updates.

In your DNS, point two names at the server:

| Name | Serves |
| --- | --- |
| `notes-mcp.example.com` | the MCP server (assistants connect here) |
| `notes.example.com` | Mycelium (you read your notes here) |

Keep them separate: different software, different logins, easier to reason about.

## 2. The vault and how it reaches your devices

Create the vault on the server, for example `/srv/vault`, owned by your user.

Your devices keep their own copy with [Syncthing](https://syncthing.net): run it on the
server (as a container or a system service) and on each computer and phone that has Obsidian,
and share the vault folder between them. A note written by the MCP server reaches every
device within seconds; a note you write in Obsidian reaches the server the same way.

(Obsidian Sync does not help here: it syncs Obsidian apps with Obsidian's cloud, and the
server is not an Obsidian app.)

Optional, recommended: keep history with Git. A systemd timer on the server that runs
`git add -A && git commit -m "auto"` in the vault every few minutes gives you every past
version of every note, without any external service.

## 3. The MCP server

```sh
git clone --branch v1.2.0 https://github.com/maxkuminov/obsidian-mcp ~/obsidian-mcp
cd ~/obsidian-mcp
make init        # creates .env and postgres.env with random database passwords
```

Edit `.env`:

```env
MCP_HOSTNAME=notes-mcp.example.com
SECRET_KEY=...                 # openssl rand -hex 32
VAULT_HOST_PATH=/srv/vault
EMBEDDING_PROVIDER=openai      # or ollama, see below
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1024
```

Embeddings power search by meaning; keyword search works without them.

- **OpenAI**: cents for the first pass over a whole vault, then near zero.
- **Ollama** on the same server or a home machine reached over a VPN (WireGuard, Tailscale):
  free, set `EMBEDDING_PROVIDER=ollama`, `OLLAMA_URL` and
  `EMBEDDING_MODEL=qwen3-embedding:0.6b`. Fine on a CPU for a vault of a few hundred notes.

Then follow the project's own guide for the rest:
[DEPLOYMENT.md](https://github.com/maxkuminov/obsidian-mcp/blob/main/DEPLOYMENT.md). The
short path is its bundled `docker-compose.simple.yml`, which runs PostgreSQL, the server and
a Caddy that gets certificates automatically:

```sh
docker run --rm caddy:2 caddy hash-password --plaintext 'a long password'
# paste the hash into Caddyfile.example (basic_auth block), then:
docker compose -f docker-compose.simple.yml up -d
```

**Do not skip the password in the Caddyfile.** In single-user mode the server relies on it to
protect the admin panel and the OAuth consent page; without it anyone could grant themselves
write access to your notes.

Check `https://notes-mcp.example.com/health` answers `"status":"ok"` and that `/admin` asks
for the password.

## 4. Mycelium

Mycelium's image (`ghcr.io/0xpietri/mycelium`) ships with v0.1.0. Once it is out, add it as a
service; it only needs the vault **read-only**, a config file and a data volume:

```yaml
services:
  mycelium:
    image: ghcr.io/0xpietri/mycelium:0.1
    restart: unless-stopped
    read_only: true
    env_file: mycelium.env            # sign-in secrets, see .env.example
    environment:
      MYCELIUM_CONFIG: /config/mycelium.toml
      MYCELIUM_VAULT: /vault
    volumes:
      - /srv/vault:/vault:ro
      - ./mycelium.toml:/config/mycelium.toml:ro
      - mycelium-data:/data
    ports:
      - "127.0.0.1:8765:8765"

volumes:
  mycelium-data:
```

And in Caddy (the bundled one, or your own):

```caddyfile
notes.example.com {
	reverse_proxy 127.0.0.1:8765
}
```

Mycelium has its own sign-in (password and authenticator app). Anonymous visitors only see
notes marked `public: true`.

If you run Caddy, Nginx or Traefik already for other sites, use the MCP project's
`docker-compose.proxy.yml` instead of the simple one and add both sites to your proxy.

## 5. Connect your assistants

- **Claude** (web, desktop and mobile, including voice mode): Settings → Connectors → Add
  custom connector, URL `https://notes-mcp.example.com/mcp`. Approve with **read + write** on
  the consent page.
- **ChatGPT**: add it as a connector in developer mode with the same URL.
- **Header-based clients** (Claude Code, scripts): create an `omcp_` API key in `/admin`.

Put a `CLAUDE.md` at the vault root describing your folders and frontmatter. Every assistant
reads it through `get_vault_guide` before writing.

## 6. Keep it healthy

- **Backups.** The vault is the only thing that matters; PostgreSQL can be rebuilt from it.
  Copy the vault (or its Git repository) off the server every night, for example pulled by a
  machine at home with `rsync` or `restic`.
- **Monitoring.** Watch the `status` field of `/health` on the MCP server (it returns HTTP 200
  even when degraded) and `/healthz` on Mycelium, with Uptime Kuma or any checker.
- **Updates.** Upgrade the MCP server by moving to a new release tag after reading its
  changelog, and Mycelium by changing its image tag. Clean old Docker images now and then
  (`docker image prune`).

## Costs, roughly

| Item | Per month |
| --- | --- |
| VPS with 2 GB of RAM | 4–6 € |
| Domain | about 1 € |
| OpenAI embeddings | a few cents, or free with Ollama |
| The assistant itself | your own Claude or ChatGPT plan |
