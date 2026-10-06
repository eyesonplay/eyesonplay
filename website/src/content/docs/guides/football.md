---
title: Football
description: Players, ball, teams, pitch calibration and football events.
---

## Detection and tracking

- **Players and ball:** YOLO. Stock COCO weights (`yolov8n`) map *person → player*
  and *sports ball → ball*; a football fine-tune with `ball`, `player`,
  `goalkeeper`, `referee` classes is better.
- **Teams:** two clusters of torso colours, kept stable and voted per track.
  The mini pitch uses each team's kit colour; teams are "A"/"B" (home/away is unknown).

## Pitch calibration

With the **Ball + Players + Pitch** model and `football-pitch-detection.pt`
(32 pitch keypoints), the worker detects landmarks every 0.4 s, fits a
homography with RANSAC and trusts it once two consecutive fits agree. Between
fits, camera pan, tilt and zoom are followed with optical flow, so calibration
holds while the camera follows the ball. Frames with too little grass
(graphics, close-ups, crowd) drop calibration at once.

## Events

| Event | When |
|---|---|
| `ball_detected`, `ball_lost`, `ball_move` | Ball presence and movement |
| `possession`, `possession_change` | Nearest player for several consecutive frames |
| `pass_candidate`, `pass` | Release, travel, a different receiver |
| `shot_candidate`, `shot` | Speed spike towards the goal mouth |
| `ball_out` | Outside the lines for several frames |
| `corner` | Ball settles in a corner arc with a player next to it |

Fields and thresholds: [Event reference](../../reference/event-schema/).
