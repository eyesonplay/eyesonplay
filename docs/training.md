# Training your own tennis bounce model

The TennisProject bounce model carries no licence, so it can only be used for
personal evaluation. This guide trains a replacement on your own labelled
matches. Your model learns from your footage, so it can also do better on it.

What you need:
- tennis videos you are allowed to use
- the dashboard (to label them)
- the native worker's Python environment with the `real` extras (catboost
  included)

Training itself takes seconds on a laptop. Most of the time goes into
labelling and into analysing each video once.

## 1. Label bounces

1. Upload the match as a tennis match.
2. On the live page, click **Label**.
3. Play the video and press **b** each time the ball touches the ground. Add
   **i** or **o** for in or out if you like; training only uses the time.
4. Saving is automatic, and the page shows how far you have labelled.
5. **Download** gives the labels as JSON. This is the same format the
   [accuracy benchmark](benchmark.md) reads.

How much to label:
- About **200–300 bounces** for a first model. That is roughly one set of one
  match, or parts of several matches.
- More matches beat more of one match, because courts, cameras and
  broadcasters differ.
- Label from the start of a stretch with no gaps. Everything up to "labelled
  up to" is treated as complete, so an unlabelled bounce there teaches the
  model that it is *not* a bounce.

The model is only as good as the labels. Press **b** on the frame of contact,
step frame by frame with `,` and `.` when unsure, and delete mistakes with
Backspace.

## 2. Train

```bash
cd inference-worker
python -m worker.training.bounce \
  --pair ~/videos/match1.mp4 ~/Downloads/match1-labels.json \
  --pair ~/videos/match2.mp4 ~/Downloads/match2-labels.json
```

The command works in five steps:

1. **Analyse.** Each video runs once through the real pipeline: TrackNet
   ball, YOLO players and court calibration, as fast as the hardware allows.
   The detections are cached in `~/.pitchside/training`, so later runs skip
   this step. On an Apple laptop GPU this takes about 4 minutes per minute of
   video, and much less on an NVIDIA GPU.
2. **Build windows.** It builds the same 5-position ball windows the event
   engine scores. The window at each labelled bounce is a positive, the
   windows right next to it are left out, and all others are negatives.
3. **Train.** It trains a CatBoost model on the **first 75%** of each
   labelled stretch and chooses its threshold.
4. **Evaluate.** On the **last 25%**, which the model has never seen, it
   replays the event engine three ways: the built-in rule, the TennisProject
   model (if installed) and your new model. Each one's events are scored
   against your labels:

   ```
   held-out events (engine replay)
   detector                 event        labels  found   prec  recall     F1
   rules                    bounce           64     71    76%     84%   0.80
   tennis_bounce.cbm        bounce           64     60    90%     84%   0.87
   tennis_bounce_own.cbm    bounce           64     62    92%     89%   0.90
   ```

   (These numbers only show the format.) Other labelled types, such as
   serves or hits, are scored too, because bounces change how points are
   called.
5. **Save.** If your model's bounce F1 is at least as good as the others, it
   is saved as `tennis_bounce_own.cbm`. Its threshold, data sources and the
   scores above go into `tennis_bounce_own.json` next to it, in the models
   folder. Use `--force` to save it anyway, or `--output-dir` to save it
   somewhere else.

The worker loads `tennis_bounce_own.cbm` first, with its threshold, and falls
back to the TennisProject model and then to the built-in rule. The model takes
effect from the next match the worker starts.

Options:

| Option | Default | |
|---|---|---|
| `--models-dir` | `~/.pitchside/models` | TrackNet, YOLO and bounce weights |
| `--held-out` | `0.25` | last part of each labelled stretch kept for evaluation |
| `--fps` | `25` | processing FPS; use what you run matches at |
| `--player-model` | `yolov8n` | YOLO weights for the players |
| `--iterations` | `800` | CatBoost trees |

## 3. Improve

- **Recall low** (bounces missed): label more matches, especially fast
  serves and far-side bounces.
- **Precision low** (bounces invented): check that the labelled stretches are
  complete. Hits near the ground are the usual confusion.
- **Low for every detector:** the ball tracker misses the ball. Check the
  "ball found" share in the match metrics. Tracking improves with a TrackNet
  trained on your footage, which is a larger job with a GPU.

Your labels and your model are yours: neither is uploaded anywhere. Keep the
label files: they are also your accuracy benchmark.
