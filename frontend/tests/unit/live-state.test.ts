import { describe, expect, it } from "vitest";

import { frameForTime, FRAME_BUFFER, FrameStore } from "@/lib/frame-store";
import { initialLiveState, liveReducer, toMatchStatus, type LiveState } from "@/lib/live-state";
import type { EventPayload, FrameData, LiveEnvelope } from "@/lib/types";

const envelope = (message: Omit<LiveEnvelope, "match_id" | "session_id" | "ts" | "seq">): LiveEnvelope =>
  ({ ...message, match_id: "m1", session_id: "s1", ts: 0, seq: 1 }) as LiveEnvelope;

const event = (id: string, type = "pass"): EventPayload => ({
  event_id: id,
  match_id: "m1",
  timestamp: 1,
  video_timestamp: 1,
  match_clock: "00:01",
  event: type,
  confidence: 0.9,
});

const frame = (n: number, t: number): FrameData => ({
  frame_number: n,
  video_timestamp: t,
  timestamp: t,
  width: 1280,
  height: 720,
  coordinate_mode: "pixel",
  ball: null,
  trail: [],
  players: [],
  latency_ms: 10,
});

const apply = (state: LiveState, message: LiveEnvelope) => liveReducer(state, { type: "message", message, receivedAt: 1 });

describe("liveReducer", () => {
  it("prepends events newest first and ignores duplicates", () => {
    let state = apply(initialLiveState, envelope({ type: "event", data: event("a") }));
    state = apply(state, envelope({ type: "event", data: event("b") }));
    state = apply(state, envelope({ type: "event", data: event("a") }));

    expect(state.events.map((e) => e.event_id)).toEqual(["b", "a"]);
  });

  it("maps worker statuses onto match statuses and surfaces failures", () => {
    const reconnecting = apply(initialLiveState, envelope({ type: "status", data: { status: "reconnecting", message: "retry 1" } }));
    expect(reconnecting.status).toBe("processing");
    expect(reconnecting.workerStatus).toBe("reconnecting");

    const failed = apply(reconnecting, envelope({ type: "status", data: { status: "failed", message: "Source gone" } }));
    expect(failed.status).toBe("failed");
    expect(failed.error).toBe("Source gone");

    const stopped = apply(failed, envelope({ type: "status", data: { status: "stopped", message: null } }));
    expect(stopped.status).toBe("completed");
    expect(stopped.error).toBeNull();
  });

  it("clears events and resets session data", () => {
    const withEvent = apply(initialLiveState, envelope({ type: "event", data: event("a") }));
    expect(liveReducer(withEvent, { type: "clear-events" }).events).toEqual([]);
    expect(liveReducer(withEvent, { type: "reset-session" }).eventIds.size).toBe(0);
  });

  it("returns null for unknown statuses", () => {
    expect(toMatchStatus("bogus")).toBeNull();
  });
});

describe("FrameStore / frameForTime", () => {
  it("keeps a bounded buffer and notifies subscribers", () => {
    const store = new FrameStore();
    let calls = 0;
    const unsubscribe = store.subscribe(() => calls++);
    for (let i = 0; i < FRAME_BUFFER + 5; i++) store.push(frame(i, i / 10));
    unsubscribe();
    store.push(frame(999, 99));

    expect(store.all()).toHaveLength(FRAME_BUFFER);
    expect(calls).toBe(FRAME_BUFFER + 5);
    expect(store.latest()?.frame_number).toBe(999);
  });

  it("picks the frame nearest the video time, else the latest", () => {
    const frames = [frame(0, 0), frame(1, 0.1), frame(2, 0.2), frame(3, 5)];
    expect(frameForTime(frames, 0.12)?.frame_number).toBe(1);
    expect(frameForTime(frames, 2.5)?.frame_number).toBe(3); // too far: latest
    expect(frameForTime(frames, null)?.frame_number).toBe(3);
    expect(frameForTime([], 1)).toBeNull();
    expect(frameForTime(frames, 2.5, 0.5, true)).toBeNull(); // strict: never the wrong moment
  });

  it("remembers the last frame with pitch coordinates for holding the mini pitch", () => {
    const store = new FrameStore();
    store.push({ ...frame(1, 0.1), coordinate_mode: "pitch" });
    store.push(frame(2, 0.2));
    expect(store.latestCalibrated()?.frame_number).toBe(1);
    store.clear();
    expect(store.latestCalibrated()).toBeNull();
  });
});
