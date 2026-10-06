# Security policy

## Supported versions

Security fixes go into the latest release. Please upgrade before reporting.

| Version | Supported |
|---|---|
| 0.1.x | ✅ |

## Reporting a vulnerability

**Do not open a public issue.** Report privately through GitHub:
[Security → Report a vulnerability](https://github.com/eyesonplay/eyesonplay/security/advisories/new).

Include what you found, how to reproduce it and the impact you expect. We aim to
acknowledge reports within 3 working days and to agree on a disclosure date
with you once a fix is ready.

## Scope notes

- The dashboard and API must run behind HTTPS in production (see
  [docs/deployment.md](docs/deployment.md)); the default compose files are for
  local development.
- Stream URLs are fetched by the worker: private and loopback hosts are refused
  unless `ALLOW_PRIVATE_SOURCES=true` (development only).
- Model weights are loaded with PyTorch; only use weights from sources you trust.
