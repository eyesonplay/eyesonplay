# Redis contract (API ⇄ worker ⇄ dashboard)

Every message is one JSON envelope:

```json
{ "type": "event", "match_id": "match_…", "session_id": "ses_…", "ts": 1760012145.32, "seq": 42, "data": { } }
```

`type` is one of `status | frame | ball | players | event | metrics | error`.

| Key / channel | Kind | Writer → reader | Purpose |
|---|---|---|---|
| `worker:commands` | stream, group `workers` | api → worker | start commands (`{command, match_id, session_id, config}`) |
| `match:{id}:control` | string | api → worker | desired state `{session_id, state: running\|paused\|stopped}` |
| `match:{id}:lease` | string, TTL 8 s | worker → api | `{worker_id, session_id}`, refreshed every second |
| `worker:{id}:heartbeat` | string, TTL 10 s | worker → api | device, GPU metrics, models, active matches, capacity |
| `status:updates` | stream, group `api-status` | worker → api | session status changes (persisted to Postgres) |
| `events:stream` | stream, group `api-persist` | worker → api | events (persisted, idempotent on `event_id`) |
| `match:{id}:status` | pub/sub | worker, api → WebSocket | `status` and `error` messages |
| `match:{id}:events` | pub/sub | worker → WebSocket | `event` messages |
| `match:{id}:detections` | pub/sub | worker → WebSocket | `frame` messages (ball, trail, players) |
| `match:{id}:metrics` | pub/sub | worker → WebSocket | `metrics` once per second |
| `match:{id}:frame:last`, `metrics:last` | string, TTL 30 s | worker → api | snapshot for newly connected clients |

Worker session statuses: `starting`, `processing`, `reconnecting`, `paused`,
`completed`, `stopped`, `failed`. The API maps them to match statuses (`stopped`
becomes `completed`, `reconnecting` becomes `processing`) and ignores updates
from superseded sessions or ones that contradict the current desired state.

## WebSocket `/ws/matches/{match_id}`

On connect the server sends a snapshot (`status`, then `frame`, `ball` and
`players` while the match is active, `metrics`, and the last 50 `event`s), then
relays the pub/sub channels above. Unknown match ids close with code `4404`.
If Redis is unavailable the server sends an `error` message and closes with
`1011`; clients reconnect with exponential backoff. Clients may send `ping`
text frames; their content is ignored.

`frame.data`:

```json
{
  "frame_number": 1221, "video_timestamp": 122.1, "timestamp": 1760012145.32,
  "width": 1280, "height": 720, "coordinate_mode": "pitch",
  "ball": { "track_id": 1, "bbox": [836, 385, 848, 397], "pixel": {"x": 842, "y": 391},
            "pitch": {"x": 72.4, "y": 38.1}, "confidence": 0.94,
            "velocity": {"x": 120.5, "y": -14.2}, "speed": 121.3, "predicted": false },
  "trail": [ {"t": 121.2, "x": 820.1, "y": 395.0, "pitch": {"x": 70.9, "y": 38.6}} ],
  "players": [ {"track_id": 42, "class": "player", "bbox": [210, 240, 268, 410],
                "confidence": 0.93, "pitch": {"x": 31.0, "y": 55.2}} ],
  "latency_ms": 183.0
}
```
