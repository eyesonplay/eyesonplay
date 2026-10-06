import { describe, expect, it } from "vitest";

import { createProjection } from "@/components/live/court-view";

const W = 800;
const H = 500;
const view = createProjection(W, H);

describe("TV-style court projection", () => {
  it("puts the near baseline at the bottom and the far baseline at the top", () => {
    const near = view.point(0, 50);
    const far = view.point(100, 50);

    expect(near.y).toBeGreaterThan(far.y);
    expect(near.x).toBeCloseTo(W / 2, 5);
    expect(far.x).toBeCloseTo(W / 2, 5);
  });

  it("draws the far end narrower, like a broadcast camera", () => {
    const nearWidth = view.point(0, 100).x - view.point(0, 0).x;
    const farWidth = view.point(100, 100).x - view.point(100, 0).x;

    expect(farWidth).toBeLessThan(nearWidth * 0.75);
    expect(view.scaleAt(100, 50)).toBeLessThan(view.scaleAt(0, 50));
  });

  it("foreshortens the far half (the net is above the middle of the baselines)", () => {
    const midway = (view.point(0, 50).y + view.point(100, 50).y) / 2;

    expect(view.point(50, 50).y).toBeLessThan(midway);
  });

  it("lifts the ball above its shadow by its height", () => {
    const ground = view.point(30, 50);
    const air = view.point(30, 50, 2);

    expect(air.x).toBeCloseTo(ground.x, 5);
    expect(ground.y - air.y).toBeCloseTo(2 * view.scaleAt(30, 50), 5);
  });

  it("keeps the whole court inside the canvas", () => {
    for (const [x, y] of [
      [0, 0],
      [0, 100],
      [100, 0],
      [100, 100],
    ]) {
      const p = view.point(x, y);
      expect(p.x).toBeGreaterThan(0);
      expect(p.x).toBeLessThan(W);
      expect(p.y).toBeGreaterThan(0);
      expect(p.y).toBeLessThan(H);
    }
  });
});
