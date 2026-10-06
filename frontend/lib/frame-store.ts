/**
 * High-rate detection frames, kept outside React state. The overlay canvas
 * reads it on every animation frame; other views subscribe with throttling.
 */

import type { FrameData } from "@/lib/types";

export const FRAME_BUFFER = 300;

type Listener = () => void;

export class FrameStore {
  private frames: FrameData[] = [];
  private lastPitchFrame: FrameData | null = null;
  private listeners = new Set<Listener>();
  private version = 0;

  push(frame: FrameData): void {
    this.frames.push(frame);
    if (frame.coordinate_mode === "pitch") this.lastPitchFrame = frame;
    if (this.frames.length > FRAME_BUFFER) this.frames.splice(0, this.frames.length - FRAME_BUFFER);
    this.version += 1;
    this.listeners.forEach((listener) => listener());
  }

  clear(): void {
    this.frames = [];
    this.lastPitchFrame = null;
    this.version += 1;
    this.listeners.forEach((listener) => listener());
  }

  all(): readonly FrameData[] {
    return this.frames;
  }

  latest(): FrameData | null {
    return this.frames.at(-1) ?? null;
  }

  /** Most recent frame that had pitch coordinates (for holding the mini pitch through gaps). */
  latestCalibrated(): FrameData | null {
    return this.lastPitchFrame;
  }

  getVersion = (): number => this.version;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };
}

/**
 * Frame to draw for the given video time: the closest buffered frame when the
 * video and the worker share a clock (uploaded/VOD sources), otherwise the latest.
 * With `strict`, nothing is returned when no frame matches the video time, so
 * boxes are never drawn over the wrong moment.
 */
export function frameForTime(
  frames: readonly FrameData[],
  videoTime: number | null,
  toleranceS = 0.5,
  strict = false,
): FrameData | null {
  if (frames.length === 0) return null;
  const latest = frames[frames.length - 1];
  if (videoTime == null) return latest;
  let best: FrameData | null = null;
  let bestDelta = Infinity;
  for (const frame of frames) {
    const delta = Math.abs(frame.video_timestamp - videoTime);
    if (delta < bestDelta) {
      best = frame;
      bestDelta = delta;
    }
  }
  if (best && bestDelta <= toleranceS) return best;
  return strict ? null : latest;
}
