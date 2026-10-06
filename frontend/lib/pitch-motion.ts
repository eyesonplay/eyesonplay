/**
 * Football mini pitch motion from analysed frames: players move smoothly
 * between frames (matched by track id) and the ball is smoothed over the
 * frames around the moment shown, which the view can do because it runs
 * behind the analysis. Only detected positions are used: a ball the tracker
 * merely predicted is not drawn, and nothing is invented across gaps.
 */

import type { Banner } from "@/lib/rally-path";
import type { EventPayload, FrameData, PlayerDetection, Point } from "@/lib/types";

export interface PitchPlayer extends Point {
  id: number | string;
  color: string;
  role: PlayerDetection["class"];
}

export interface PitchScene {
  players: PitchPlayer[];
  ball: Point | null;
  heldFor: number | null; // seconds since calibration was lost (last positions shown)
}

export const HOLD_S = 15; // last calibrated positions stay (faded) through close-ups
const MAX_GAP_S = 0.8; // frames further apart are not interpolated
const BALL_WINDOW_S = 0.2; // ball smoothing half-window
export const UNASSIGNED = "#a1a1aa";
export const REFEREE = "#18181b";
export const KEEPER = "#f97316";

const EMPTY: PitchScene = { players: [], ball: null, heldFor: null };

export function pitchSceneAt(frames: readonly FrameData[], t: number): PitchScene {
  const calibrated = frames.filter((f) => f.coordinate_mode === "pitch");
  const after = calibrated.findIndex((f) => f.video_timestamp >= t);
  const a = after === -1 ? calibrated.at(-1) : after > 0 ? calibrated[after - 1] : null;
  const b = after === -1 ? null : calibrated[after];
  if (b && (!a || b.video_timestamp === t)) {
    return b.video_timestamp - t <= MAX_GAP_S
      ? { players: located(b), ball: ballAt(calibrated, t), heldFor: null }
      : EMPTY;
  }
  if (!a) return EMPTY;
  if (b && b.video_timestamp - a.video_timestamp <= MAX_GAP_S) {
    const s = (t - a.video_timestamp) / (b.video_timestamp - a.video_timestamp);
    return { players: blend(located(a), located(b), s), ball: ballAt(calibrated, t), heldFor: null };
  }
  const heldFor = t - a.video_timestamp;
  if (heldFor <= MAX_GAP_S) return { players: located(a), ball: ballAt(calibrated, t), heldFor: null };
  return heldFor <= HOLD_S ? { players: located(a), ball: null, heldFor } : EMPTY;
}

function located(frame: FrameData): PitchPlayer[] {
  const teams = frame.teams ?? [];
  return frame.players.flatMap((p, i) => {
    if (!p.pitch) return [];
    const team = p.team != null ? teams.find((tm) => tm.id === p.team) : undefined;
    const color = p.class === "referee" ? REFEREE : (team?.color ?? (p.class === "goalkeeper" ? KEEPER : UNASSIGNED));
    return [{ id: p.track_id ?? `u${i}`, x: p.pitch.x, y: p.pitch.y, color, role: p.class }];
  });
}

/** Players in both frames glide between them; the rest appear from the nearer frame. */
function blend(from: PitchPlayer[], to: PitchPlayer[], s: number): PitchPlayer[] {
  const next = new Map(to.map((p) => [p.id, p]));
  const moving = from.flatMap((p) => {
    const q = next.get(p.id);
    if (!q) return s < 0.5 ? [p] : [];
    return [{ ...q, x: p.x + (q.x - p.x) * s, y: p.y + (q.y - p.y) * s }];
  });
  const known = new Set(from.map((p) => p.id));
  const arriving = s >= 0.5 ? to.filter((q) => !known.has(q.id)) : [];
  return [...moving, ...arriving];
}

/** Weighted average of detected ball positions within the window around t. */
function ballAt(calibrated: readonly FrameData[], t: number): Point | null {
  let sx = 0;
  let sy = 0;
  let total = 0;
  for (const f of calibrated) {
    const dt = Math.abs(f.video_timestamp - t);
    const pitch = f.ball && !f.ball.predicted ? f.ball.pitch : null;
    if (dt > BALL_WINDOW_S || !pitch) continue;
    const w = 1 - dt / (BALL_WINDOW_S + 1e-6);
    sx += pitch.x * w;
    sy += pitch.y * w;
    total += w;
  }
  return total > 0 ? { x: sx / total, y: sy / total } : null;
}

const FOOTBALL_CALLS: Record<string, Omit<Banner, "t">> = {
  shot: { text: "Shot", tone: "neutral" },
  shot_candidate: { text: "Shot", tone: "neutral" },
  ball_out: { text: "Ball out", tone: "out" },
  corner: { text: "Corner", tone: "neutral" },
  goal: { text: "Goal", tone: "in" },
};

/** Calls worth a banner on the mini pitch, in time order (events arrive newest first). */
export function footballBanners(events: readonly EventPayload[]): Banner[] {
  return events
    .flatMap((e) => {
      const call = FOOTBALL_CALLS[e.event];
      if (!call) return [];
      const score = e.event === "goal" ? (e.score as { home?: number; away?: number } | undefined) : undefined;
      const text = score ? `${call.text} · ${score.home}–${score.away}` : call.text;
      return [{ t: e.video_timestamp, ...call, text }];
    })
    .sort((a, b) => a.t - b.t);
}

export const CORNER_SHOW_S = 6;
const CORNER_FLAGS: Record<string, Point> = {
  top_left: { x: 0, y: 0 },
  top_right: { x: 100, y: 0 },
  bottom_left: { x: 0, y: 100 },
  bottom_right: { x: 100, y: 100 },
};

export interface ActiveCorner extends Point {
  age: number; // seconds since the corner was detected
}

/** The corner flag to highlight at time t: the latest detected corner, for a few seconds. */
export function activeCorner(events: readonly EventPayload[], t: number): ActiveCorner | null {
  let best: ActiveCorner | null = null;
  for (const e of events) {
    const flag = e.event === "corner" && typeof e.corner === "string" ? CORNER_FLAGS[e.corner] : undefined;
    const age = t - e.video_timestamp;
    if (!flag || age < 0 || age > CORNER_SHOW_S || (best && best.age <= age)) continue;
    best = { ...flag, age };
  }
  return best;
}
