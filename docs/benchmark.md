# Accuracy benchmark

How well does EyesOnPlay detect events on *your* footage? Label a stretch of a
match by hand, export what EyesOnPlay detected, and score one against the other.

## 1. Label a match

Watch the video (the dashboard player shows the video time) and write each
event you see into a JSON file. Times are seconds of video.

```json
{
  "sport": "tennis",
  "source": "Beijing 2026 R1, 1080p broadcast, first 2 minutes, labelled by A. Smith",
  "labelled_until_s": 120,
  "events": [
    { "t": 0.48, "event": "serve", "player": "near" },
    { "t": 0.80, "event": "bounce", "in": true },
    { "t": 1.16, "event": "hit", "player": "far" },
    { "t": 15.16, "event": "point_won", "winner": "near" }
  ]
}
```

- Use the event names from the [event reference](event-schema.md).
- Only label the event types you want scored; other detected types are ignored.
- `labelled_until_s` is where your labelling stops, so detections after it
  don't count as false positives.
- Any extra field (`in`, `player`, `winner`, `corner`, …) is checked on the
  events that were found, as *detail accuracy*.

An example file is in [benchmarks/example-tennis.json](benchmarks/example-tennis.json).

## 2. Export the detections

Process the same video, then on the match's live page use **Download all
events (JSON)** in the JSON inspector (or `GET /api/matches/{id}/events/export`).
This gives a JSON array of events.

## 3. Score

```bash
cd event-engine
python -m eop_benchmark labels.json match-events.json            # table
python -m eop_benchmark labels.json match-events.json --json     # for CI or notebooks
python -m eop_benchmark labels.json match-events.json --tolerance 0.3
```

```
event            labels  found   prec  recall     F1  Δt (s)  details
bounce               32     30    90%     84%   0.87    0.06  in 93%
hit                  23     21    95%     87%   0.91    0.11  player 100%
serve                 5      5   100%    100%   1.00    0.20  player 100%
```

- **precision:** of the events found, how many really happened.
- **recall:** of the events that happened, how many were found.
- **Δt:** average timing error of the matched events.
- A detection matches the closest unmatched label of the same type within
  `--tolerance` seconds (default 0.5).

(The numbers above illustrate the format; they are not a published result.)

## Tips

- Label at least a few full points or several minutes of open play per match,
  and several matches, before drawing conclusions.
- Keep labels with the video name and resolution: results depend on the camera,
  the broadcast and the processing FPS (tennis needs 25 fps).
- Commit label files you are allowed to share to `docs/benchmarks/` so results
  can be reproduced.
