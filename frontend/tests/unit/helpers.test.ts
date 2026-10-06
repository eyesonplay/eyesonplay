import { describe, expect, it } from "vitest";

import {
  clockToSeconds,
  matchFormSchema,
  secondsToClock,
  toMatchInput,
  defaultValues,
} from "@/components/matches/form-schema";
import { uncalibratedReason } from "@/components/live/mini-pitch";
import { eventGroup, eventSummary, filtersFor, matchesFilter } from "@/lib/events";
import { formatBytes, formatFixed, formatVideoTime, sourceSummary } from "@/lib/format";

describe("event taxonomy", () => {
  it("groups types for filters", () => {
    expect(eventGroup("shot_candidate")).toBe("shot");
    expect(eventGroup("unknown")).toBeNull();
    expect(matchesFilter("possession_change", "possession")).toBe(true);
    expect(matchesFilter("pass", "all")).toBe(true);
    expect(matchesFilter("pass", "shot")).toBe(false);
  });

  it("summarises payloads without inventing identities", () => {
    expect(
      eventSummary({ event: "pass", from_track_id: 12, to_track_id: 27, distance: 18.4, distance_unit: "m" }),
    ).toBe("#12 → #27 · 18.4m");
    expect(eventSummary({ event: "pass", from_track_id: 1, to_track_id: 2, distance: 9, distance_unit: "m" })).toBe(
      "#1 → #2 · 9.0m",
    );
    expect(eventSummary({ event: "ball_out", side: "left" })).toBe("left line");
    expect(
      eventSummary({
        event: "goal",
        team: "away",
        score: { home: 1, away: 2 },
        evidence: ["scoreboard", "goal_graphic"],
      }),
    ).toBe("away · 1–2 · scoreboard + goal graphic");
    expect(eventSummary({ event: "goal_candidate", goal: "right" })).toBe("ball in the right goal (unconfirmed)");
    expect(eventGroup("goal_candidate")).toBe("goal");
  });
});

describe("formatters", () => {
  it("formats numbers, sizes and times", () => {
    expect(formatFixed(null)).toBe("—");
    expect(formatFixed(12.345, 1, " fps")).toBe("12.3 fps");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatVideoTime(3725)).toBe("1:02:05");
    expect(sourceSummary("hls", "https://cdn.example.com/live/match.m3u8?token=x")).toBe(
      "cdn.example.com/live/match.m3u8",
    );
    expect(sourceSummary("upload", "uploads/abc.mp4")).toBe("abc.mp4");
  });
});

describe("match form schema", () => {
  const base = { ...defaultValues(), name: "A vs B", home_team: "A", away_team: "B" };

  it("validates source URLs per type", () => {
    expect(matchFormSchema.safeParse({ ...base, video_source: "ftp://x" }).success).toBe(false);
    expect(matchFormSchema.safeParse({ ...base, video_source_type: "rtmp", video_source: "https://x" }).success).toBe(
      false,
    );
    expect(matchFormSchema.safeParse({ ...base, video_source: "https://x/live.m3u8" }).success).toBe(true);
    expect(matchFormSchema.safeParse({ ...base, video_source: "" }).success).toBe(true); // draft
  });

  it("converts to API input respecting model dependencies", () => {
    const input = toMatchInput({ ...base, detection_model: "ball", video_source: "", kickoff_clock: "45:00" });
    expect(input.video_source_type).toBeNull();
    expect(input.enable_player_tracking).toBe(false);
    expect(input.enable_pitch_mapping).toBe(false);
    expect(input.kickoff_offset_seconds).toBe(2700);
  });

  it("round-trips the match clock", () => {
    expect(secondsToClock(clockToSeconds("72:14"))).toBe("72:14");
  });
});

describe("mini pitch calibration reason", () => {
  it("explains each uncalibrated state", () => {
    expect(uncalibratedReason({ state: "no_model" })).toContain("not installed");
    expect(uncalibratedReason({ state: "searching", keypoints: 2 })).toContain("2 visible");
    expect(uncalibratedReason({ state: "disabled" })).toContain("off for this match");
    expect(uncalibratedReason(undefined)).toContain("unavailable");
  });
});

describe("tennis events", () => {
  it("groups and filters tennis events", () => {
    expect(eventGroup("double_fault")).toBe("serve");
    expect(eventGroup("point_won")).toBe("point");
    expect(matchesFilter("ball_out", "out")).toBe(true);
    expect(filtersFor("tennis").map((f) => f.key)).toEqual(["all", "serve", "hit", "bounce", "out", "point"]);
    expect(filtersFor("football").some((f) => f.key === "possession")).toBe(true);
  });

  it("summarises tennis payloads", () => {
    expect(eventSummary({ event: "bounce", in: false, side: "far" })).toBe("OUT · far");
    expect(eventSummary({ event: "point_won", winner: "near", reason: "double_bounce", rally_length: 5 })).toBe(
      "near wins · double bounce · rally 5",
    );
    expect(eventSummary({ event: "serve", player: "far", serve_number: 2, court: "ad" })).toBe(
      "far · serve 2 · ad court",
    );
  });
});
