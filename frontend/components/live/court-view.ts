/**
 * TV-style view of the tennis court for the mini court: the near baseline at
 * the bottom, the far baseline at the top, in perspective like the broadcast
 * camera. Court coordinates: x 0-100 along from the near baseline, y 0-100
 * across (y = 0 on the left of the picture).
 */

import { createPerspective, type Projection } from "@/components/live/perspective";

export type { Projection, ScreenPoint } from "@/components/live/perspective";

export const COURT_L_M = 23.77;
export const COURT_W_M = 10.97;
const RUNOFF_ALONG = 18; // % of court length shown behind each baseline
const RUNOFF_ACROSS = 14; // % of court width shown beside each sideline

export function createProjection(width: number, height: number): Projection {
  const near = -RUNOFF_ALONG;
  const far = 100 + RUNOFF_ALONG;
  const left = -RUNOFF_ACROSS;
  const right = 100 + RUNOFF_ACROSS;
  return createPerspective(width, height, {
    corners: [
      [near, left],
      [near, right],
      [far, right],
      [far, left],
    ],
    farWidth: 0.52,
    marginTop: 0.16, // room for the far player standing well behind the baseline
    marginBottom: 0.02,
    metre: [0, 100 / COURT_W_M],
  });
}
