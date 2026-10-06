---
title: How it works
description: From a video stream to live events and a mini view.
---

```
Video (HLS / RTMP / URL / upload)
  ─▶ FFmpeg decode at the processing FPS
  ─▶ detection: YOLO (players, ball), TrackNet (tennis ball), pitch keypoints / court lines
  ─▶ tracking: Kalman ball tracker, IoU + motion player tracker, teams by shirt colour
  ─▶ calibration: image ↔ pitch/court homography, kept through camera pans
  ─▶ event engine (rules, no I/O): football or tennis
  ─▶ Redis streams + pub/sub ─▶ API (FastAPI) ─▶ WebSocket ─▶ dashboard / integration feed
```

## Services

| Service | Stack | Role |
|---|---|---|
| **frontend** | Next.js, TypeScript, Tailwind | Dashboard: matches, live view, events, settings |
| **api** | FastAPI, PostgreSQL, Redis | REST + WebSocket, sign-in, persistence, processing control |
| **worker** | Python, FFmpeg, PyTorch | Decoding, detection, tracking, calibration, events (CPU, CUDA or Apple MPS) |
| **event engine** | Pure Python | Football and tennis rules, unit tested without video |

Inference runs in its own service so GPU workers scale independently; each
worker takes up to `MAX_CONCURRENT_MATCHES` matches from a Redis consumer group.

## Principles

- **Never invent data.** Without calibration, positions stay in pixels and
  pitch coordinates are `null`. A ball the tracker only predicted is not drawn.
  Point endings in tennis are held briefly and cancelled if play continues.
- **Confidence on everything.** Events carry a confidence; shots are only
  `shot` above a threshold, otherwise `shot_candidate`.
- **Reliable control.** Start, pause, stop and restart are desired states the
  worker polls, so commands are never lost; workers hold leases and a
  watchdog fails matches whose worker disappears.

## The mini view

The TV-style mini pitch and mini court are drawn from tracking data only.
Players glide between analysed frames (matched by track), the football is
smoothed over neighbouring frames, and tennis shots are drawn between the
detected hits and bounces. Ball height in tennis is drawn, not measured. The
view follows the video clock, and while processing the video is paced to the
analysis so both always show the same moment.
