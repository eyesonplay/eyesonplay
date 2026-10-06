/**
 * A tennis rally as a ball path for the mini court, built only from detected
 * events and player positions: hits start at the hitter's feet, bounces are
 * where the ball landed. Between them the ball moves in a straight ground
 * line; its height is a drawn arc (the worker does not measure height), so
 * it shows the shot, not a measurement. Gaps too long for one shot (missed
 * detections) are left empty rather than invented.
 */

import type { EventPayload, FrameData, Point } from "@/lib/types";

export type KeyframeKind = "serve" | "hit" | "bounce";

export interface Keyframe {
  t: number;
  kind: KeyframeKind;
  x: number; // normalised court units (0-100 along, 0-100 across)
  y: number;
  in?: boolean | null; // bounces only
  side?: "near" | "far"; // hits and serves: who played it
}

export interface BallPoint extends Point {
  height: number; // metres, drawn arc
}

export interface CourtPlayers {
  near: Point | null;
  far: Point | null;
}

const MAX_SHOT_S = 2.2; // longer gaps mean a missed hit or bounce
const HITTER_LOOKUP_S = 0.3; // frame used for the hitter's position must be this close
const CONTACT_M = 1.0;
const SERVE_CONTACT_M = 2.7;
const COURT_LENGTH_M = 23.77;
const COURT_WIDTH_M = 10.97;

/** Keyframes in time order from events (newest first) and buffered frames. */
export function buildKeyframes(events: readonly EventPayload[], frames: readonly FrameData[]): Keyframe[] {
  const keys: Keyframe[] = [];
  for (const e of events) {
    const key = toKeyframe(e, frames);
    if (key) keys.push(key);
  }
  return keys.sort((a, b) => a.t - b.t);
}

function toKeyframe(e: EventPayload, frames: readonly FrameData[]): Keyframe | null {
  const t = e.video_timestamp;
  if (e.event === "bounce") {
    const loc = asPoint(e.location);
    return loc
      ? {
          t,
          kind: "bounce",
          x: loc.x,
          y: loc.y,
          in: typeof e.in === "boolean" ? e.in : null,
        }
      : null;
  }
  if (e.event !== "hit" && e.event !== "serve") return null;
  const side = e.player === "near" || e.player === "far" ? e.player : null;
  if (!side) return null;
  const located = frames.some(
    (f) => f.coordinate_mode === "pitch" && Math.abs(f.video_timestamp - t) <= HITTER_LOOKUP_S,
  );
  const feet = located ? playersAt(frames, t)[side] : null;
  return feet ? { t, kind: e.event, x: feet.x, y: feet.y, side } : null;
}

function asPoint(value: unknown): Point | null {
  if (!value || typeof value !== "object") return null;
  const { x, y } = value as Record<string, unknown>;
  return typeof x === "number" && typeof y === "number" ? { x, y } : null;
}

/** Where the ball is at time t, or null when the path is unknown. */
export function ballAt(keys: readonly Keyframe[], t: number): BallPoint | null {
  const next = keys.findIndex((k) => k.t >= t);
  if (next === -1) return null;
  if (next === 0) return keys[0].t === t ? groundAt(keys[0]) : null;
  const a = keys[next - 1];
  const b = keys[next];
  if (b.t - a.t > MAX_SHOT_S) return null;
  const s = (t - a.t) / (b.t - a.t);
  return {
    x: a.x + (b.x - a.x) * s,
    y: a.y + (b.y - a.y) * s,
    height: arcHeight(a, b, s),
  };
}

function groundAt(k: Keyframe): BallPoint {
  return { x: k.x, y: k.y, height: startHeight(k) };
}

function startHeight(k: Keyframe): number {
  if (k.kind === "serve") return SERVE_CONTACT_M;
  return k.kind === "hit" ? CONTACT_M : 0;
}

function arcHeight(a: Keyframe, b: Keyframe, s: number): number {
  const h0 = startHeight(a);
  const h1 = b.kind === "bounce" ? 0 : CONTACT_M;
  const lift = a.kind === "bounce" ? 0.6 : a.kind === "serve" ? 0.3 : shotLift(a, b);
  return h0 * (1 - s) + h1 * s + 4 * lift * s * (1 - s);
}

/** Longer shots fly higher over the net. */
function shotLift(a: Keyframe, b: Keyframe): number {
  const dx = ((b.x - a.x) / 100) * COURT_LENGTH_M;
  const dy = ((b.y - a.y) / 100) * COURT_WIDTH_M;
  return Math.min(2.0, Math.max(0.4, 0.06 * Math.hypot(dx, dy)));
}

/** Near and far player feet at time t, interpolated between calibrated frames. */
export function playersAt(frames: readonly FrameData[], t: number): CourtPlayers {
  const calibrated = frames.filter((f) => f.coordinate_mode === "pitch");
  if (calibrated.length === 0) return { near: null, far: null };
  const after = calibrated.findIndex((f) => f.video_timestamp >= t);
  const b = after === -1 ? calibrated[calibrated.length - 1] : calibrated[after];
  const a = after > 0 ? calibrated[after - 1] : b;
  const pa = sides(a);
  const pb = sides(b);
  const span = b.video_timestamp - a.video_timestamp;
  const s = span > 0 ? Math.min(1, Math.max(0, (t - a.video_timestamp) / span)) : 1;
  return {
    near: lerpPoint(pa.near, pb.near, s),
    far: lerpPoint(pa.far, pb.far, s),
  };
}

/** The near player is the one closer to x = 0. */
function sides(frame: FrameData): CourtPlayers {
  const located = frame.players.flatMap((p) => (p.pitch && p.class !== "referee" ? [p.pitch] : []));
  if (located.length === 0) return { near: null, far: null };
  const sorted = [...located].sort((p, q) => p.x - q.x);
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  if (sorted.length === 1) return first.x < 50 ? { near: first, far: null } : { near: null, far: first };
  return { near: first, far: last };
}

function lerpPoint(a: Point | null, b: Point | null, s: number): Point | null {
  if (a && b) return { x: a.x + (b.x - a.x) * s, y: a.y + (b.y - a.y) * s };
  return s < 0.5 ? a : b;
}

export interface Banner {
  t: number;
  text: string;
  tone: "neutral" | "in" | "out";
}

const REASON_LABEL: Record<string, string> = {
  out: "out",
  net: "net",
  double_bounce: "winner", // bounced twice: the receiver did not reach it
  not_returned: "not returned",
  double_fault: "double fault",
};

/** Short on-court calls (serve, fault, point) in time order. */
export function buildBanners(events: readonly EventPayload[]): Banner[] {
  const banners: Banner[] = [];
  for (const e of events) {
    const banner = toBanner(e);
    if (banner) banners.push(banner);
  }
  return banners.sort((a, b) => a.t - b.t);
}

function toBanner(e: EventPayload): Banner | null {
  const t = e.video_timestamp;
  const who = sideName(e.player);
  switch (e.event) {
    case "serve":
      return {
        t,
        text: `${e.serve_number === 2 ? "Second serve" : "Serve"} · ${who}`,
        tone: "neutral",
      };
    case "fault":
      return { t, text: `Fault · ${who}`, tone: "out" };
    case "double_fault":
      return { t, text: `Double fault · ${who}`, tone: "out" };
    case "point_won": {
      const reason = typeof e.reason === "string" ? REASON_LABEL[e.reason] : undefined;
      return {
        t,
        text: `Point ${sideName(e.winner)}${reason ? ` · ${reason}` : ""}`,
        tone: "in",
      };
    }
    default:
      return null;
  }
}

function sideName(side: unknown): string {
  if (side === "near") return "Near";
  if (side === "far") return "Far";
  return "?";
}
