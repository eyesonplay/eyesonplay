---
title: Limitations and FAQ
description: What EyesOnPlay does not do yet, and honest numbers.
---

## Current results

Measured on one 1080p broadcast clip each, not yet a labelled benchmark:

- **Tennis:** court calibrated in 88% of frames (the rest are close-ups and
  replays), ball found in 71%, both players identified in 86%.
- **Football:** pitch calibrated in 50–75% of broadcast frames in our tests; positions
  are approximate (a few metres).

A benchmark against hand-labelled matches is on the roadmap.

## Not yet

- Player identities, names and team home/away (no identity model).
- Ball height in football; forehand/backhand in tennis.
- Goals, throw-ins, free kicks, fouls and offside.
- Real time on a laptop GPU for tennis at 25 fps.

## FAQ

**Does it need cameras in the stadium?** No, one broadcast-style video.

**Does it guess when it cannot see?** No. Unknown positions are `null`, and the
dashboard says why (close-up, no calibration, no model).

**Can I use it commercially?** Under the AGPL, or with a commercial licence. See
[Licensing](../licensing/).
