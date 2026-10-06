import { describe, expect, it } from "vitest";

import { activeCorner, footballBanners, pitchSceneAt } from "@/lib/pitch-motion";
import type { EventPayload, FrameData, PlayerDetection } from "@/lib/types";

function player(trackId: number, x: number, y: number, team: number | null = 0): PlayerDetection {
  return { track_id: trackId, class: "player", bbox: [0, 0, 1, 1], confidence: 0.9, pitch: { x, y }, team };
}

function frame(
  t: number,
  players: PlayerDetection[],
  ball: { x: number; y: number } | null = null,
  mode: "pitch" | "pixel" = "pitch",
): FrameData {
  return {
    frame_number: Math.round(t * 25),
    video_timestamp: t,
    coordinate_mode: mode,
    ball: ball ? { pixel: { x: 0, y: 0 }, pitch: ball, predicted: false } : null,
    trail: [],
    players,
    teams: [{ id: 0, label: "A", color: "#ff0000" }],
  } as unknown as FrameData;
}

describe("football pitch motion", () => {
  it("moves each player smoothly between frames, matched by track", () => {
    const frames = [
      frame(0, [player(7, 10, 20), player(9, 60, 50)]),
      frame(0.4, [player(9, 64, 50), player(7, 14, 24)]),
    ];

    const scene = pitchSceneAt(frames, 0.1);

    const seven = scene.players.find((p) => p.id === 7)!;
    expect(seven.x).toBeCloseTo(11, 5);
    expect(seven.y).toBeCloseTo(21, 5);
    expect(seven.color).toBe("#ff0000");
    expect(scene.players.find((p) => p.id === 9)!.x).toBeCloseTo(61, 5);
    expect(scene.heldFor).toBeNull();
  });

  it("smooths the ball over the frames around the moment shown", () => {
    const frames = [0, 0.04, 0.08, 0.12, 0.16].map((t, i) => frame(t, [], { x: 50 + (i % 2 === 0 ? 1 : -1), y: 40 }));

    const ball = pitchSceneAt(frames, 0.08).ball!;

    expect(Math.abs(ball.x - 50)).toBeLessThan(0.6); // the zig-zag of detection noise is averaged out
    expect(ball.y).toBeCloseTo(40, 5);
  });

  it("does not draw a ball that was only predicted, never detected", () => {
    const predicted = { ...frame(0, [], { x: 50, y: 40 }) };
    (predicted.ball as { predicted: boolean }).predicted = true;

    expect(pitchSceneAt([predicted], 0).ball).toBeNull();
  });

  it("holds the last calibrated players, without a ball, through a close-up", () => {
    const frames = [frame(0, [player(7, 10, 20)], { x: 30, y: 30 }), frame(2, [], null, "pixel")];

    const scene = pitchSceneAt(frames, 2);

    expect(scene.heldFor).toBeCloseTo(2, 5);
    expect(scene.players.map((p) => p.id)).toEqual([7]);
    expect(scene.ball).toBeNull();
  });

  it("shows nothing once the hold has run out", () => {
    const frames = [frame(0, [player(7, 10, 20)]), frame(30, [], null, "pixel")];

    expect(pitchSceneAt(frames, 30).players).toEqual([]);
  });
});

describe("football calls", () => {
  const event = (t: number, type: string) => ({ event: type, video_timestamp: t }) as EventPayload;

  it("shows shots, the ball going out and goals in time order, and skips the rest", () => {
    const banners = footballBanners([event(9, "ball_out"), event(4, "pass"), event(3, "shot_candidate")]);

    expect(banners).toEqual([
      { t: 3, text: "Shot", tone: "neutral" },
      { t: 9, text: "Ball out", tone: "out" },
    ]);
  });
});

describe("corner highlight", () => {
  const corner = (t: number, name: string) =>
    ({ event: "corner", video_timestamp: t, corner: name }) as unknown as EventPayload;

  it("highlights the corner where the ball was placed, for a few seconds", () => {
    const events = [corner(10, "bottom_right"), corner(2, "top_left")];

    expect(activeCorner(events, 11)).toEqual({ x: 100, y: 100, age: 1 });
    expect(activeCorner(events, 3.5)).toEqual({ x: 0, y: 0, age: 1.5 });
  });

  it("shows nothing before the corner or long after it", () => {
    const events = [corner(10, "top_right")];

    expect(activeCorner(events, 9)).toBeNull();
    expect(activeCorner(events, 30)).toBeNull();
  });
});

describe("goal calls", () => {
  it("shows the new score on the goal banner", () => {
    const goal = {
      event: "goal",
      video_timestamp: 12,
      team: "home",
      score: { home: 2, away: 1 },
    } as unknown as EventPayload;

    expect(footballBanners([goal])).toEqual([{ t: 12, text: "Goal · 2–1", tone: "in" }]);
  });
});
