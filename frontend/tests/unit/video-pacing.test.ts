import { describe, expect, it } from "vitest";

import { RateMeter, pace } from "@/lib/video-pacing";

describe("video pacing", () => {
  it("plays at the analysis rate when the video is exactly the lead behind", () => {
    expect(pace({ videoTime: 9, analysedTime: 10, analysisRate: 0.32 })).toEqual({ kind: "rate", rate: 0.32 });
  });

  it("slows down when the video is slightly ahead of the analysis", () => {
    const decision = pace({ videoTime: 9.1, analysedTime: 10, analysisRate: 0.32 });

    expect(decision.kind).toBe("rate");
    expect(decision.kind === "rate" && decision.rate).toBeLessThan(0.32);
  });

  it("waits for the analysis instead of playing moments it has not analysed", () => {
    expect(pace({ videoTime: 10.5, analysedTime: 10, analysisRate: 0.32 })).toEqual({ kind: "hold" });
  });

  it("waits at the start until the first frame is analysed", () => {
    expect(pace({ videoTime: 0.2, analysedTime: null, analysisRate: 1 })).toEqual({ kind: "hold" });
  });

  it("speeds up, within limits, when the video falls behind", () => {
    const decision = pace({ videoTime: 7, analysedTime: 10, analysisRate: 1 });

    expect(decision).toEqual({ kind: "rate", rate: 2 });
  });

  it("jumps when the gap is too large to catch up smoothly", () => {
    expect(pace({ videoTime: 0, analysedTime: 30, analysisRate: 1 })).toEqual({
      kind: "seek",
      to: 29,
    });
    expect(pace({ videoTime: 40, analysedTime: 30, analysisRate: 1 })).toEqual({
      kind: "seek",
      to: 29,
    });
  });
});

describe("analysis rate", () => {
  it("measures video seconds analysed per wall second", () => {
    const meter = new RateMeter();
    meter.sample(10, 0);
    meter.sample(10.32, 1000);
    meter.sample(10.64, 2000);

    expect(meter.rate()).toBeCloseTo(0.32, 5);
  });

  it("assumes real time until there is enough history", () => {
    const meter = new RateMeter();
    meter.sample(10, 0);

    expect(meter.rate()).toBe(1);
  });

  it("starts over when the analysis restarts from an earlier time", () => {
    const meter = new RateMeter();
    meter.sample(50, 0);
    meter.sample(51, 1000);
    meter.sample(0, 2000);

    expect(meter.rate()).toBe(1);
  });
});
