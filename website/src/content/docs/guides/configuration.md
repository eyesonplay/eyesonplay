---
title: Configuration
description: Environment variables for the API, worker and dashboard.
---

Copy [`.env.example`](https://github.com/eyesonplay/eyesonplay/blob/main/.env.example)
to `.env`. Local development works with the defaults.

| Variable | Service | Default | |
|---|---|---|---|
| `DOMAIN` | caddy | — | Production domain (HTTPS) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | api | dev account | First dashboard user, created on startup if missing |
| `POSTGRES_PASSWORD` | postgres, api | `football` | Set your own before the first production start |
| `INFERENCE_MODE` | worker | `mock` | `mock` or `real` |
| `MAX_CONCURRENT_MATCHES` | worker | `4` | Matches per worker |
| `ALLOW_PRIVATE_SOURCES` | worker | `false` | Allow stream URLs on private hosts (development only) |
| `CORS_ORIGINS` | api | `http://localhost:3000` | Dashboard origins, comma separated |
| `COOKIE_SECURE` | api | `false` | Session cookie over HTTPS only; `true` in production |
| `SESSION_TTL_HOURS` | api | `336` | Sign-in lifetime |
| `FEED_REQUESTS_PER_MINUTE` | api | `120` | Integration feed limit per API key |
| `MAX_UPLOAD_MB` | api | `4096` | Largest upload |
| `NEXT_PUBLIC_API_URL` | frontend (build) | empty | Empty: `<host>:8000`; `same-origin` behind a reverse proxy |
| `BIND_ADDRESS` | dev compose | `127.0.0.1` | Where the dev ports listen |
| `BACKUP_DIR`, `BACKUP_KEEP_DAYS` | backup | `./backups`, `14` | Nightly database dumps |
