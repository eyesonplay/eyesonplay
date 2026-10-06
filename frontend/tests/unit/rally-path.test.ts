import { describe, expect, it } from "vitest";

import { ballAt, buildBanners, buildKeyframes, playersAt } from "@/lib/rally-path";
import type { EventPayload, FrameData, PlayerDetection } from "@/lib/types";

function player(trackId: number, x: number, y: number): PlayerDetection {
  return {
    track_id: trackId,
    class: "player",
    bbox: [0, 0, 1, 1],
    confidence: 0.9,
    pitch: { x, y },
  };
}

function frame(t: number, players: PlayerDetection[]): FrameData {
  return {
    frame_number: Math.round(t * 25),
    video_timestamp: t,
    coordinate_mode: "pitch",
    ball: null,
    trail: [],
    players,
  } as unknown as FrameData;
}

function event(t: number, type: string, extra: Record<string, unknown> = {}): EventPayload {
  return {
    event_id: `${type}-${t}`,
    match_id: "m",
    timestamp: t,
    video_timestamp: t,
    match_clock: "0:00",
    event: type,
    confidence: 0.8,
    ...extra,
  } as EventPayload;
}

const NEAR = (x: number, y = 60) => player(1, x, y);
const FAR = (x: number, y = 40) => player(2, x, y);
const frames = [0, 0.5, 1, 1.5, 2].map((t) => frame(t, [NEAR(2 + t), FAR(97 - t)]));

// Events arrive newest first, as in the live state.
const SERVE_BOUNCE_RETURN = [
  event(1.4, "hit", { player: "far", track_id: 2 }),
  event(0.8, "bounce", { location: { x: 75, y: 40 }, in: true }),
  event(0.2, "serve", { player: "near", track_id: 1 }),
];

describe("rally keyframes", () => {
  it("places hits at the hitter's feet and bounces where they landed", () => {
    const keys = buildKeyframes(SERVE_BOUNCE_RETURN, frames);

    expect(keys.map((k) => k.kind)).toEqual(["serve", "bounce", "hit"]);
    expect(keys[0].x).toBeCloseTo(2.2, 1);
    expect(keys[1]).toMatchObject({ x: 75, y: 40, in: true });
    expect(keys[2].x).toBeCloseTo(95.6, 1);
  });

  it("skips hits whose hitter was not located instead of guessing", () => {
    expect(buildKeyframes([event(9, "hit", { player: "far", track_id: 2 })], frames)).toEqual([]);
  });
});

describe("ball position", () => {
  const keys = buildKeyframes(SERVE_BOUNCE_RETURN, frames);

  it("travels between keyframes and is on the ground at the bounce", () => {
    const mid = ballAt(keys, 0.5)!;
    const atBounce = ballAt(keys, 0.8)!;

    expect(mid.x).toBeGreaterThan(keys[0].x);
    expect(mid.x).toBeLessThan(75);
    expect(mid.height).toBeGreaterThan(0);
    expect(atBounce.x).toBeCloseTo(75, 5);
    expect(atBounce.height).toBeCloseTo(0, 5);
  });

  it("is hidden before the first and after the last keyframe", () => {
    expect(ballAt(keys, 0.1)).toBeNull();
    expect(ballAt(keys, 3)).toBeNull();
  });

  it("is hidden across gaps too long to be one shot (missed detections)", () => {
    const gap = buildKeyframes(
      [event(5, "bounce", { location: { x: 20, y: 50 } }), event(1, "bounce", { location: { x: 80, y: 50 } })],
      frames,
    );

    expect(ballAt(gap, 3)).toBeNull();
  });
});

describe("players", () => {
  it("interpolates the near and far player between frames", () => {
    const at = playersAt(frames, 0.25);

    expect(at.near?.x).toBeCloseTo(2.25, 5);
    expect(at.far?.x).toBeCloseTo(96.75, 5);
  });

  it("knows nothing about players in uncalibrated frames", () => {
    const pixelOnly = [{ ...frames[0], coordinate_mode: "pixel" } as FrameData];

    expect(playersAt(pixelOnly, 0)).toEqual({ near: null, far: null });
  });
});

describe("call banners", () => {
  it("names serves and points in time order, folding the reason into the point", () => {
    const banners = buildBanners([
      event(3.0, "point_won", { winner: "near", reason: "out" }),
      event(3.0, "ball_out", { player: "far" }),
      event(0.2, "serve", { player: "near", serve_number: 2 }),
      event(0.8, "bounce", { location: { x: 75, y: 40 } }),
    ]);

    expect(banners).toEqual([
      { t: 0.2, text: "Second serve · Near", tone: "neutral" },
      { t: 3.0, text: "Point Near · out", tone: "in" },
    ]);
  });

  it("shows faults as out calls", () => {
    expect(buildBanners([event(1, "double_fault", { player: "far" })])).toEqual([
      { t: 1, text: "Double fault · Far", tone: "out" },
    ]);
  });
});
