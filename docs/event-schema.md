# Event schema

All events share these fields (`team` and `player` are always `null` until an
identity model exists):

```json
{
  "event_id": "evt_01K…", "match_id": "match_…", "timestamp": 1760012145.32,
  "video_timestamp": 2493.4, "frame": 24934, "match_clock": "41:33",
  "event": "ball_move", "confidence": 0.94, "team": null, "player": null,
  "ball": { "pixel": {"x": 842, "y": 391}, "pitch": {"x": 72.4, "y": 38.1}, "confidence": 0.94 }
}
```

`ball.pitch` is normalised 0–100 on both axes, and `null` without pitch
calibration. Locations inside events carry `coordinate_space: "pitch" | "pixel"`.
`match_clock` = `video_timestamp` + the match's kickoff offset.

| Event | Extra fields | Rule (thresholds in `EngineConfig`) |
|---|---|---|
| `ball_detected` | — | ball visible after being lost or at start |
| `ball_lost` | `missing_frames` | no ball for `ball_lost_after_frames` frames |
| `ball_move` | `velocity`, `speed`, `coordinate_space` | at most once per `ball_move_min_interval_s`, and only after moving a minimum distance |
| `possession` | `track_id` | nearest player within `possession_radius` for `possession_confirm_frames` consecutive frames |
| `possession_change` | `from_track_id`, `to_track_id` | a new holder differs from the last holder |
| `pass_candidate` | `from_track_id`, `start` | the ball leaves the holder faster than `pass_candidate_min_speed` |
| `pass` | `from_track_id`, `to_track_id`, `start`, `end`, `distance`, `distance_unit`, `duration` | release, then travel ≥ `pass_min_distance`, then a different player confirmed within `pass_max_duration_s`; deduplicated |
| `shot_candidate` | `track_id`, `location`, `speed`, `speed_unit`, `target_goal`, `distance_to_goal_m` | speed spike within `shot_origin_window_s` of a touch, heading into the goal mouth (pitch mode). Pixel mode: confidence capped at `shot_no_pitch_max_confidence` |
| `shot` | as `shot_candidate` | only when confidence ≥ `shot_confirm_confidence` |
| `ball_out` | `side`, `location`, `last_touch_track_id`, `within_goal_mouth` | outside the pitch for `ball_out_frames` frames (pitch coordinates only) |

Planned: `goal`, `corner`, `throw_in`, `goal_kick`, `free_kick`, `cross`,
`tackle`, `interception`, `save`.
