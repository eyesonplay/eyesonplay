# Changelog

## Unreleased

### Training
- Labelling page: mark serves, hits, bounces, faults and points (tennis) or
  goals, corners, shots and passes (football) with the keyboard while the
  video plays; autosaved, exported in the benchmark format.
- Train your own tennis bounce model from labelled matches
  (`python -m worker.training.bounce`, see docs/training.md): the real
  pipeline is recorded once per video, the model is evaluated against the
  built-in rule and the installed model on held-out labels, and the worker
  prefers it automatically.

### Football
- Goals: the broadcast scoreboard is read on screen (RapidOCR) and a score that
  goes up by one is a `goal` for that team, timed at the "GOAL" graphic or the
  ball crossing the line when seen. The ball crossing the goal line between the
  posts alone is a `goal_candidate`.

## 0.1.0 — first release

Real-time sports video analysis for football and tennis, from a single
broadcast camera.

### Platform
- Matches from live streams (HLS/RTMP), video URLs or uploaded files; start,
  pause, resume, stop and restart processing from the dashboard.
- FastAPI REST + WebSocket API, PostgreSQL, Redis streams and pub/sub; a worker
  that runs in Docker (mock or CPU/GPU) or natively (e.g. Apple MPS).
- Integration feed for external systems, with API keys (created and revoked in
  Settings) and external match links; rate limited per key.
- Dashboard sign-in: Argon2id passwords, HttpOnly session cookies, cross-site
  request protection, sign-in rate limits, user management CLI.
- Live dashboard: video with detection overlay, event feed with filters, JSON
  inspector, metrics bar; video and mini view side by side, paced to the
  analysis so both show the same moment.

### Deployment
- Production compose file: Caddy with automatic HTTPS on one origin, security
  headers and body limits, required secrets, nightly database backups.
- Docker images for the API, dashboard and workers (CPU, GPU) published to
  GitHub Container Registry on every release.
- Website with documentation, and an accuracy benchmark to score detected
  events against hand-labelled matches.

### Football
- Ball and player detection (YOLO), Kalman ball tracking, player tracking.
- Automatic pitch calibration from pitch keypoints, kept while the camera pans.
- Teams by shirt colour.
- Events: ball detected/lost/moving, possession, passes, shots, ball out, corners.
- TV-style animated mini pitch: players in team colours, smoothed ball,
  corner-flag highlight.

### Tennis
- Classical court-line calibration, restored on the first wide frame after a
  close-up.
- TrackNet ball tracking and bounce detection (model weights not included).
- Events: serve, hit, bounce (in/out), fault, double fault, ball out, point won.
- TV-style animated mini court: players, ball arc with shadow, bounce marks,
  call banners.

### Known limitations
- Not real time on a laptop GPU for tennis at 25 fps; an NVIDIA GPU is needed
  for live use.
- Accuracy has not been benchmarked against hand-labelled matches yet.
- Tennis model weights from TennisProject carry no licence: personal
  evaluation only (see [docs/third-party.md](docs/third-party.md)).
