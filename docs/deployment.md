# Deploying EyesOnPlay

This guide runs EyesOnPlay on one server with HTTPS, a login-protected
dashboard, a GPU worker and nightly database backups. Everything runs with
Docker Compose.

## What you need

- A Linux server with Docker Engine and the Compose plugin (v2.24 or newer).
- For live analysis, an NVIDIA GPU with the
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
  (L4, A10 or T4 class; tennis at 25 fps needs a GPU to keep up with real time).
  Without a GPU, use the CPU worker for testing only.
- A domain name, e.g. `eyes.example.com`, with an `A`/`AAAA` record pointing
  at the server, and ports 80 and 443 open (HTTPS certificates are issued
  automatically by Caddy through Let's Encrypt).

## 1. Configure

```bash
git clone https://github.com/eyesonplay/eyesonplay.git && cd eyesonplay
cp .env.example .env
```

Set at least these in `.env`:

| Variable | Example | |
|---|---|---|
| `DOMAIN` | `eyes.example.com` | The dashboard URL; DNS must already point here |
| `ADMIN_EMAIL` | `you@example.com` | First dashboard user, created on first start |
| `ADMIN_PASSWORD` | a long random password | At least 10 characters; change it later with the CLI |
| `POSTGRES_PASSWORD` | a long random password | Set **before** the first start (Postgres keeps the first one) |
| `INFERENCE_MODE` | `real` | `mock` runs the simulation instead of video analysis |

Generate passwords with `openssl rand -base64 24`.

## 2. Models

The worker loads model weights from the `models` volume. Copy the files you
use (see [third-party.md](third-party.md) for sources and licences):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml -f docker-compose.prod.yml \
  run --rm --no-deps -v "$PWD/models:/in:ro" worker sh -c 'cp /in/* /data/models/'
```

The stock YOLO weights (`yolov8n.pt`) download automatically on first use.

## 3. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml -f docker-compose.prod.yml up -d --build
```

Open `https://<DOMAIN>` and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
Database migrations run automatically when the API starts.

What the production file changes compared with local development:

- **Caddy** serves the dashboard and the API on one HTTPS origin, renews the
  certificate, and adds HSTS and other security headers. The API (8000) and
  dashboard (3000) ports are not published.
- The session cookie is sent over HTTPS only (`COOKIE_SECURE=true`) and
  cross-site requests are refused.
- A `backup` service dumps the database every day.

## 4. Users

```bash
alias eop='docker compose -f docker-compose.yml -f docker-compose.gpu.yml -f docker-compose.prod.yml'
eop exec api python -m app.cli create-user coach@example.com   # asks for a password
eop exec api python -m app.cli set-password you@example.com
eop exec api python -m app.cli disable-user coach@example.com  # signs them out everywhere
eop exec api python -m app.cli list-users
```

Sessions last 14 days (`SESSION_TTL_HOURS`). After 5 failed sign-ins for one
email, or 20 attempts from one IP address, sign-in is paused for 15 minutes.

## 5. Integrations

Other systems read matches and live events through the
[integration feed](integration-feed.md) with an API key created in the dashboard
(**Settings → API keys**). Keys are shown once and stored hashed; each key may
make 120 requests per minute (`FEED_REQUESTS_PER_MINUTE`).

## 6. Backups and restore

Dumps are written to `BACKUP_DIR` (default `./backups`) as
`eyesonplay-<UTC time>.dump` and kept for `BACKUP_KEEP_DAYS` (default 14). Copy
them off the server (e.g. `rclone`, `restic`) — a backup on the same disk does
not survive losing the disk.

Restore a dump into a running stack:

```bash
eop exec -T postgres pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB" < backups/eyesonplay-20261006T020000Z.dump
```

Uploaded videos live in the `media` volume and are not part of the database
dump; back that volume up separately if you need the source files.

## 7. Updates

```bash
git pull
eop up -d --build
```

Read [CHANGELOG.md](../CHANGELOG.md) before upgrading. Migrations run on start;
take a backup first (`eop exec backup sh -c 'pg_dump -Fc > /backups/before-upgrade.dump'`).

## 8. Operations

- **Health:** `https://<DOMAIN>/api/system/live` (no login) for uptime checks;
  the dashboard's **System** page shows workers, GPUs and models.
- **Logs:** JSON lines on stdout: `eop logs -f api worker`.
- **Scaling:** add GPU workers on other machines pointed at the same Redis and
  media storage; each takes up to `MAX_CONCURRENT_MATCHES` matches.

## Security checklist

- [ ] `DOMAIN`, `ADMIN_PASSWORD` and `POSTGRES_PASSWORD` set to your own values
- [ ] Only ports 80 and 443 open to the internet (not 5432, 6379, 8000 or 3000)
- [ ] Backups copied off the server and a restore tested
- [ ] `ALLOW_PRIVATE_SOURCES=false` (the default) so stream URLs cannot reach your internal network
- [ ] Model weights only from sources you trust (PyTorch weights can run code when loaded)
- [ ] Commercial use checked against [third-party.md](third-party.md) (YOLO is AGPL-3.0)
