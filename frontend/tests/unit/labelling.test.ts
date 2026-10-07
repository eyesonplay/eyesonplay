import { describe, expect, it } from "vitest";

import { applyKey, formatLabelTime, type Label } from "@/lib/labelling";

describe("labelling keys", () => {
  it("marks an event at the current video time, keeping labels in time order", () => {
    const start: Label[] = [{ t: 9, event: "hit" }];

    const result = applyKey(start, "b", 4.567, "tennis")!;

    expect(result.labels).toEqual([
      { t: 4.57, event: "bounce" },
      { t: 9, event: "hit" },
    ]);
    expect(result.message).toBe("bounce at 0:04.57");
    expect(start).toEqual([{ t: 9, event: "hit" }]); // never mutated
  });

  it("tags the label just marked with near/far, in/out or home/away", () => {
    let labels = applyKey([], "s", 1, "tennis")!.labels;
    labels = applyKey(labels, "2", 1.4, "tennis")!.labels;
    labels = applyKey(labels, "b", 2, "tennis")!.labels;
    labels = applyKey(labels, "o", 2.1, "tennis")!.labels;

    expect(labels).toEqual([
      { t: 1, event: "serve", player: "far" },
      { t: 2, event: "bounce", in: false },
    ]);

    const goal = applyKey(applyKey([], "g", 30, "football")!.labels, "1", 31, "football")!;
    expect(goal.labels).toEqual([{ t: 30, event: "goal", team: "home" }]);
  });

  it("only sets details that make sense for the event", () => {
    const bounce = applyKey([], "b", 2, "tennis")!.labels;

    const result = applyKey(bounce, "1", 2.2, "tennis")!;

    expect(result.labels).toEqual(bounce);
    expect(result.message).toMatch(/nothing to tag/i);
  });

  it("names the point winner, not the player, on a point", () => {
    const point = applyKey([], "p", 10, "tennis")!.labels;

    expect(applyKey(point, "1", 10.5, "tennis")!.labels).toEqual([{ t: 10, event: "point_won", winner: "near" }]);
  });

  it("removes the label just marked with Backspace", () => {
    const labels: Label[] = [
      { t: 1, event: "serve" },
      { t: 2, event: "bounce" },
    ];

    expect(applyKey(labels, "Backspace", 2.5, "tennis")!.labels).toEqual([{ t: 1, event: "serve" }]);
  });

  it("ignores keys that mean nothing for the sport", () => {
    expect(applyKey([], "g", 1, "tennis")).toBeNull();
    expect(applyKey([], "x", 1, "football")).toBeNull();
  });

  it("formats label times as minutes, seconds and hundredths", () => {
    expect(formatLabelTime(65.32)).toBe("1:05.32");
    expect(formatLabelTime(3725.5)).toBe("62:05.50");
  });
});
