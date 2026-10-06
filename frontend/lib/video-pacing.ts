/**
 * Keeps an uploaded/VOD video in step with the analysis, so the picture,
 * the detection overlay and the mini court show the same moment even when
 * the worker analyses slower than real time. The video trails the newest
 * analysed frame by LEAD_S so events about that moment have arrived.
 */

export const LEAD_S = 1.0;
const GAIN = 0.8; // playback-rate correction per second of error
const MIN_RATE = 0.0625; // browsers' lowest supported playbackRate
const MAX_RATE = 2;
const SEEK_S = 4; // further off than this: jump instead of catching up
const HOLD_AHEAD_S = 0.3; // further ahead than this: wait for the analysis
const WINDOW_MS = 3000;

export type PaceDecision = { kind: "rate"; rate: number } | { kind: "seek"; to: number } | { kind: "hold" };

export function pace({
  videoTime,
  analysedTime,
  analysisRate,
}: {
  videoTime: number;
  analysedTime: number | null; // newest analysed frame; null before the first one
  analysisRate: number;
}): PaceDecision {
  if (analysedTime === null) return { kind: "hold" };
  const target = Math.max(0, analysedTime - LEAD_S);
  const behind = target - videoTime;
  if (Math.abs(behind) > SEEK_S) return { kind: "seek", to: target };
  if (behind < -HOLD_AHEAD_S) return { kind: "hold" };
  const rate = Math.min(MAX_RATE, Math.max(MIN_RATE, analysisRate + GAIN * behind));
  return { kind: "rate", rate: Math.round(rate * 1000) / 1000 };
}

/** Video seconds analysed per wall-clock second, over a short window. */
export class RateMeter {
  private samples: { ts: number; wall: number }[] = [];

  sample(ts: number, wallMs: number): void {
    const last = this.samples.at(-1);
    if (last && ts < last.ts) this.samples = []; // a new session started over
    if (last && ts === last.ts) return;
    this.samples = [...this.samples.filter((s) => wallMs - s.wall <= WINDOW_MS), { ts, wall: wallMs }];
  }

  rate(): number {
    const first = this.samples[0];
    const last = this.samples.at(-1);
    if (!first || !last || this.samples.length < 3 || last.wall <= first.wall) return 1;
    return (last.ts - first.ts) / ((last.wall - first.wall) / 1000);
  }
}
