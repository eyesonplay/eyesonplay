# Third-party software and models

EyesOnPlay is licensed under the GNU AGPL-3.0 (see [LICENSE](../LICENSE)), with
commercial licences available. This page lists what it builds on, under which
licence, and which model weights are **not** distributed with the project.

Versions are those in use at release 0.1.0; licences are taken from each
package's own metadata. Check them again before shipping a commercial build.

## Model weights (not included in this repository)

No model weights are committed. The worker loads them from `MODELS_DIR`
(default `~/.pitchside/models` for the native worker, `/data/models` in Docker).

| File | Used for | Source | Licence | Status |
|---|---|---|---|---|
| `yolov8n.pt`, `yolov8s.pt` | Players and ball (COCO) | Ultralytics, downloaded automatically | AGPL-3.0 | Usable under AGPL; a commercial closed-source product needs an [Ultralytics Enterprise licence](https://www.ultralytics.com/license) or another detector |
| `football-player-detection.pt`, `football-ball-detection.pt`, `football-pitch-detection.pt` | Football players/ball, pitch keypoints | [roboflow/sports](https://github.com/roboflow/sports) | Code MIT; YOLO-based weights trained on Roboflow Universe datasets | Check the training datasets' licences and the Ultralytics licence before commercial use |
| `tracknet_ball.pt` | Tennis ball (TrackNet) | [yastrebksv/TennisProject](https://github.com/yastrebksv/TennisProject) | **No licence published** | **Personal evaluation only.** Not redistributable; must be replaced with your own trained model before any release that ships weights or any commercial use |
| `tennis_bounce.cbm` | Tennis bounce classifier (CatBoost) | [yastrebksv/TennisProject](https://github.com/yastrebksv/TennisProject) | **No licence published** | Same as above. Without it the engine falls back to its built-in bounce rule |
| `tennis_bounce_own.cbm` | Tennis bounce classifier (CatBoost), preferred when present | Trained by you on your labelled matches ([docs/training.md](training.md)) | Yours | Replaces `tennis_bounce.cbm` |

The network definition in `inference-worker/worker/detect/tracknet.py` is our
own implementation of the published TrackNet architecture (it only mirrors the
layer names so compatible weights load).

## Python packages

| Package | Version | Licence | Used by |
|---|---|---|---|
| fastapi | 0.142 | MIT | api |
| uvicorn | 0.54 | BSD-3-Clause | api |
| sqlalchemy | 2.1 | MIT | api |
| asyncpg | 0.31 | Apache-2.0 | api |
| alembic | 1.20 | MIT | api |
| python-multipart | 0.0.32 | Apache-2.0 | api |
| pydantic, pydantic-settings | 2.13, 2.15 | MIT | api, worker |
| redis (redis-py) | 8.1 | MIT | api, worker |
| structlog | 26.1 | MIT OR Apache-2.0 | api, worker |
| numpy | 2.5 | BSD-3-Clause (and bundled permissive licences) | worker |
| opencv-python-headless | 5.0 | Apache-2.0 | worker (real mode) |
| **ultralytics** | 8.4 | **AGPL-3.0** | worker (real mode) |
| torch | 2.14 | Apache-2.0 (per package metadata) | worker (real mode, via ultralytics) |
| torchvision | 0.29 | BSD | worker (real mode) |
| catboost | 1.2 | Apache-2.0 | worker (optional, tennis bounces) |
| rapidocr | 3.9 | Apache-2.0 | worker (real mode, scoreboard OCR for goals; bundles PaddleOCR ONNX models, Apache-2.0) |
| onnxruntime | 1.2x | MIT | worker (real mode, runs the OCR models) |
| scipy | 1.18 | BSD | worker (real mode, via ultralytics) |
| nvidia-ml-py | 13.6 | BSD | worker (GPU metrics) |

The event engine (`event-engine/`) has no runtime dependencies.

## JavaScript packages (frontend)

| Package | Version | Licence |
|---|---|---|
| next | 16.3 | MIT |
| react, react-dom | 19.2 | MIT |
| @base-ui/react | 1.8 | MIT |
| shadcn | 4.21 | MIT |
| tailwindcss | 4.3 | MIT |
| tw-animate-css | 1.4 | MIT |
| class-variance-authority | 0.7 | Apache-2.0 |
| @tanstack/react-query | 5.104 | MIT |
| @tanstack/react-virtual | 3.14 | MIT |
| react-hook-form, @hookform/resolvers | 7.89, 5.9 | MIT |
| zod | 4.6 | MIT |
| hls.js | 1.7 | Apache-2.0 |
| lucide-react | 1.52 | ISC |
| next-themes | 0.4 | MIT |
| sonner | 2.0 | MIT |

## Services and tools (run alongside, not linked)

| Component | Licence | Note |
|---|---|---|
| PostgreSQL (`postgres:16-alpine`) | PostgreSQL License | |
| Redis (`redis:7-alpine`) | Redis 7.4+: RSALv2 / SSPLv1 (earlier 7.x: BSD-3-Clause) | Fine to run unmodified as your own backing service; it may not be offered to others as a managed Redis service. [Valkey](https://valkey.io) (BSD-3-Clause) is a drop-in alternative |
| FFmpeg | LGPL-2.1+ / GPL-2.0+ depending on the build | Called as a separate program; the Debian packages in the images are GPL builds |
| NVIDIA CUDA images | NVIDIA Deep Learning Container licence | GPU image only |
