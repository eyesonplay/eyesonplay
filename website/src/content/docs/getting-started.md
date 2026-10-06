---
title: Getting started
description: Run EyesOnPlay locally in a few minutes, with a simulated match and no GPU.
---

## Try it with the simulation (no GPU)

You need [Docker](https://docs.docker.com/get-docker/) with Compose.

```bash
git clone https://github.com/eyesonplay/eyesonplay.git
cd eyesonplay
docker compose up --build
```

Open <http://localhost:3000> and sign in with the local development account
**admin@example.com** / **eyesonplay-admin**.

1. Click **New match**.
2. Paste any HLS URL, for example `https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8`.
3. Press **Create & start processing**.

The worker runs in `INFERENCE_MODE=mock`: a simulated football match (or tennis
rally, if you choose tennis) is projected through a synthetic broadcast camera
and fed through the **real** tracking and event pipeline. Every part of the
dashboard works, but the detections are not related to the video's content.

| URL | |
|---|---|
| <http://localhost:3000> | Dashboard |
| <http://localhost:8000/docs> | API docs (OpenAPI) |
| `ws://localhost:8000/ws/matches/{id}` | Live feed (signed in) |

## Analyse real video

Real analysis needs model weights and, for live speed, a GPU:

```bash
# NVIDIA GPU (needs the NVIDIA Container Toolkit)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
# CPU (slow, any machine)
docker compose -f docker-compose.yml -f docker-compose.real.yml up --build
```

Then set the match's sport and detection model:

- **Football:** *Ball + Players + Pitch* with the pitch keypoint model for the mini pitch.
- **Tennis:** *Ball + Players + Court*, 25 fps.

See [Football](../guides/football/), [Tennis](../guides/tennis/) and
[Third-party software and models](../reference/third-party/) for the weights.

On a Mac, Docker cannot use the Apple GPU. Run the worker natively against the
Docker stack instead; the [README](https://github.com/eyesonplay/eyesonplay#docker-stack--native-gpu-worker-mac)
has the commands.

## Next

- [How it works](../guides/how-it-works/)
- [Deploy to production](../reference/deployment/)
- [Integration feed](../reference/integration-feed/)
