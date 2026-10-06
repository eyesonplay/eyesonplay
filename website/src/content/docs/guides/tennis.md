---
title: Tennis
description: Court calibration, ball tracking, bounces and scoring from broadcast tennis.
---

## Court

Classical line detection, no model and no licence constraints: a white-line
mask, Hough lines and a court template scored line by line. Broadcast tennis
cameras return to the same framing after close-ups, so the last good fit is
re-checked on every frame and restored on the first wide frame.

## Ball and bounces

- **Ball:** a TrackNet heatmap network over three consecutive frames.
- **Bounces:** a CatBoost classifier over the ball's trajectory, with a built-in
  rule as fallback.
- Use **25 fps**: at 12 fps most bounces are lost. A laptop GPU runs about 3x
  slower than real time; use an NVIDIA GPU for live matches.

The TrackNet and bounce weights published by
[TennisProject](https://github.com/yastrebksv/TennisProject) carry no licence:
use them for personal evaluation only. See
[Third-party software and models](../../reference/third-party/).

## Scoring logic

- **Serve:** counted once the ball crosses the net, stamped at the hit.
- **Hit:** the ball reverses away from a player within reach.
- **Bounce in/out:** the first bounce after a shot decides. A ball that lands in
  and then bounces again (even past the baseline) is a winner, not out.
- **Point endings** are held for 0.8 s and cancelled if the other player plays the ball.

Players are `near` and `far` (the camera's view): names and forehand/backhand
need identity and handedness, which are not known.
