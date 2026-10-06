/**
 * Canvas drawing for the mini court replay, TV style: the court in
 * perspective with the near player at the bottom and the far player at the
 * top, a net with height, standing players, the ball above its shadow,
 * bounce marks and short call banners. Pure functions of the scene; the
 * component owns the clock and the animation loop.
 */

import { COURT_W_M, createProjection, type Projection, type ScreenPoint } from "@/components/live/court-view";
import { ballAt, type Banner, type CourtPlayers, type Keyframe } from "@/lib/rally-path";

export const PLAYER_COLORS = { near: "#38bdf8", far: "#f472b6" } as const;
const SURROUND = "#1e5470";
const SURFACE = "#2b6aa0";
const LINE = "rgba(255,255,255,0.9)";
const BALL = "#e4f442";
const IN = "#34d399";
const OUT = "#fb7185";

// Court lines in normalised units (x along from the near baseline, y across).
const SINGLES = (1.37 / COURT_W_M) * 100;
const SERVICE_NEAR = 50 - (6.4 / 23.77) * 100;
const SERVICE_FAR = 50 + (6.4 / 23.77) * 100;
const POST = (0.914 / COURT_W_M) * 100; // net posts stand outside the doubles lines
const NET_POST_M = 1.07;
const NET_CENTRE_M = 0.914;

const BODY_W_M = 0.55;
const BODY_H_M = 1.45;
const HEAD_R_M = 0.17;
const BALL_R_M = 0.2; // drawn larger than a real ball (6.7 cm) to stay visible
const TAIL_STEPS = 7;
const TAIL_STEP_S = 0.035;
const HIT_FLASH_S = 0.35;
const RIPPLE_S = 0.6;
const MARK_LIFETIME_S = 10;
const MAX_MARKS = 6;
const BANNER_S = 1.8;

export interface Scene {
  t: number;
  keys: readonly Keyframe[];
  players: CourtPlayers;
  banners: readonly Banner[];
  dimmed: boolean; // calibration lost: last known state, faded
}

type Draw = (ctx: CanvasRenderingContext2D, view: Projection) => void;

export function drawScene(ctx: CanvasRenderingContext2D, width: number, height: number, scene: Scene): void {
  const view = createProjection(width, height);
  ctx.clearRect(0, 0, width, height);
  drawCourt(ctx, view, width, height);
  ctx.globalAlpha = scene.dimmed ? 0.35 : 1;
  drawBounceMarks(ctx, view, scene);
  // Farther things first, so nearer ones (and the net) cover them.
  const layers: { depth: number; draw: Draw }[] = [{ depth: 50, draw: drawNet }];
  for (const side of ["near", "far"] as const) {
    const at = scene.players[side];
    if (at) layers.push({ depth: at.x, draw: (c, v) => drawPlayer(c, v, scene, side, at.x, at.y) });
  }
  const ball = ballAt(scene.keys, scene.t);
  if (ball) layers.push({ depth: ball.x - 0.01, draw: (c, v) => drawBall(c, v, scene) });
  for (const layer of layers.sort((a, b) => b.depth - a.depth)) layer.draw(ctx, view);
  ctx.globalAlpha = 1;
  drawBanner(ctx, width, height, scene.t, scene.banners);
}

function polygon(ctx: CanvasRenderingContext2D, points: ScreenPoint[]): void {
  ctx.beginPath();
  points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.closePath();
}

function line(ctx: CanvasRenderingContext2D, view: Projection, x1: number, y1: number, x2: number, y2: number): void {
  const a = view.point(x1, y1);
  const b = view.point(x2, y2);
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.stroke();
}

function drawCourt(ctx: CanvasRenderingContext2D, view: Projection, width: number, height: number): void {
  const sky = ctx.createLinearGradient(0, 0, 0, height);
  sky.addColorStop(0, "#0b1d2a");
  sky.addColorStop(1, "#102a3a");
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = SURROUND;
  polygon(ctx, [view.point(-18, -14), view.point(-18, 114), view.point(118, 114), view.point(118, -14)]);
  ctx.fill();
  ctx.fillStyle = SURFACE;
  polygon(ctx, [view.point(0, 0), view.point(0, 100), view.point(100, 100), view.point(100, 0)]);
  ctx.fill();
  ctx.strokeStyle = LINE;
  ctx.lineWidth = Math.max(1, view.scaleAt(50, 50) * 0.06);
  polygon(ctx, [view.point(0, 0), view.point(0, 100), view.point(100, 100), view.point(100, 0)]);
  ctx.stroke();
  line(ctx, view, 0, SINGLES, 100, SINGLES);
  line(ctx, view, 0, 100 - SINGLES, 100, 100 - SINGLES);
  line(ctx, view, SERVICE_NEAR, SINGLES, SERVICE_NEAR, 100 - SINGLES);
  line(ctx, view, SERVICE_FAR, SINGLES, SERVICE_FAR, 100 - SINGLES);
  line(ctx, view, SERVICE_NEAR, 50, SERVICE_FAR, 50);
  line(ctx, view, 0, 50, 1.3, 50);
  line(ctx, view, 98.7, 50, 100, 50);
}

function drawNet(ctx: CanvasRenderingContext2D, view: Projection): void {
  const left = -POST;
  const right = 100 + POST;
  const top = [view.point(50, left, NET_POST_M), view.point(50, 50, NET_CENTRE_M), view.point(50, right, NET_POST_M)];
  ctx.fillStyle = "rgba(8,15,22,0.45)";
  polygon(ctx, [view.point(50, left), view.point(50, right), top[2], top[1], top[0]]);
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,0.95)";
  ctx.lineWidth = Math.max(1.5, view.scaleAt(50, 50) * 0.07);
  ctx.beginPath();
  top.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.stroke();
  ctx.strokeStyle = "rgba(220,220,220,0.9)";
  for (const y of [left, right]) {
    const foot = view.point(50, y);
    const head = view.point(50, y, NET_POST_M);
    ctx.beginPath();
    ctx.moveTo(foot.x, foot.y);
    ctx.lineTo(head.x, head.y);
    ctx.stroke();
  }
}

function drawBounceMarks(ctx: CanvasRenderingContext2D, view: Projection, scene: Scene): void {
  const marks = scene.keys
    .filter((key) => key.kind === "bounce" && key.t <= scene.t && scene.t - key.t < MARK_LIFETIME_S)
    .slice(-MAX_MARKS);
  const base = ctx.globalAlpha;
  for (const mark of marks) {
    const age = scene.t - mark.t;
    const p = view.point(mark.x, mark.y);
    const s = view.scaleAt(mark.x, mark.y);
    const color = mark.in === false ? OUT : IN;
    ctx.globalAlpha = base * Math.max(0.25, 1 - age / MARK_LIFETIME_S);
    if (mark.in === false) {
      drawCross(ctx, p, 0.3 * s, color);
    } else {
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.ellipse(p.x, p.y, 0.28 * s, 0.13 * s, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    if (age < RIPPLE_S) {
      const grow = age / RIPPLE_S;
      ctx.globalAlpha = base * (1 - grow);
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(1, 0.06 * s);
      ctx.beginPath();
      ctx.ellipse(p.x, p.y, (0.3 + 1.0 * grow) * s, (0.14 + 0.45 * grow) * s, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
  ctx.globalAlpha = base;
}

function drawCross(ctx: CanvasRenderingContext2D, p: ScreenPoint, r: number, color: string): void {
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(1.5, r * 0.4);
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(p.x - r, p.y - r * 0.45);
  ctx.lineTo(p.x + r, p.y + r * 0.45);
  ctx.moveTo(p.x - r, p.y + r * 0.45);
  ctx.lineTo(p.x + r, p.y - r * 0.45);
  ctx.stroke();
}

function drawPlayer(
  ctx: CanvasRenderingContext2D,
  view: Projection,
  scene: Scene,
  side: "near" | "far",
  x: number,
  y: number,
): void {
  const feet = view.point(x, y);
  const s = view.scaleAt(x, y);
  ctx.fillStyle = "rgba(0,0,0,0.35)";
  ctx.beginPath();
  ctx.ellipse(feet.x + 0.15 * s, feet.y, 0.5 * s, 0.18 * s, 0, 0, Math.PI * 2);
  ctx.fill();
  drawHitFlash(ctx, view, scene, side, x, y);
  ctx.fillStyle = PLAYER_COLORS[side];
  ctx.strokeStyle = "rgba(255,255,255,0.9)";
  ctx.lineWidth = Math.max(1, 0.05 * s);
  ctx.beginPath();
  ctx.roundRect(feet.x - (BODY_W_M / 2) * s, feet.y - BODY_H_M * s, BODY_W_M * s, (BODY_H_M - 0.05) * s, 0.2 * s);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(feet.x, feet.y - (BODY_H_M + HEAD_R_M + 0.04) * s, HEAD_R_M * s, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
}

function drawHitFlash(
  ctx: CanvasRenderingContext2D,
  view: Projection,
  scene: Scene,
  side: "near" | "far",
  x: number,
  y: number,
): void {
  const hit = scene.keys.findLast((key) => key.side === side && key.t <= scene.t);
  if (!hit || scene.t - hit.t > HIT_FLASH_S) return;
  const grow = (scene.t - hit.t) / HIT_FLASH_S;
  const p = view.point(x, y);
  const s = view.scaleAt(x, y);
  const base = ctx.globalAlpha;
  ctx.globalAlpha = base * (1 - grow);
  ctx.strokeStyle = BALL;
  ctx.lineWidth = Math.max(1.5, 0.08 * s);
  ctx.beginPath();
  ctx.ellipse(p.x, p.y, (0.7 + 1.0 * grow) * s, (0.3 + 0.4 * grow) * s, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.globalAlpha = base;
}

function drawBall(ctx: CanvasRenderingContext2D, view: Projection, scene: Scene): void {
  const ball = ballAt(scene.keys, scene.t);
  if (!ball) return;
  const s = view.scaleAt(ball.x, ball.y);
  const base = ctx.globalAlpha;
  const shadow = view.point(ball.x, ball.y);
  const lift = Math.min(ball.height, 4);
  ctx.globalAlpha = base * (0.5 - lift * 0.07);
  ctx.fillStyle = "#000";
  ctx.beginPath();
  ctx.ellipse(shadow.x, shadow.y, BALL_R_M * (1 - lift * 0.08) * s, BALL_R_M * 0.45 * s, 0, 0, Math.PI * 2);
  ctx.fill();
  // Tapered streak along the same analytic path: smooth, never a scribble.
  ctx.strokeStyle = BALL;
  ctx.lineCap = "round";
  let prev = view.point(ball.x, ball.y, ball.height);
  for (let i = 1; i <= TAIL_STEPS; i += 1) {
    const past = ballAt(scene.keys, scene.t - i * TAIL_STEP_S);
    if (!past) break;
    const at = view.point(past.x, past.y, past.height);
    const fade = 1 - i / (TAIL_STEPS + 1);
    ctx.globalAlpha = base * 0.5 * fade;
    ctx.lineWidth = Math.max(1, BALL_R_M * 1.6 * fade * s);
    ctx.beginPath();
    ctx.moveTo(prev.x, prev.y);
    ctx.lineTo(at.x, at.y);
    ctx.stroke();
    prev = at;
  }
  const p = view.point(ball.x, ball.y, ball.height);
  ctx.globalAlpha = base;
  ctx.fillStyle = BALL;
  ctx.strokeStyle = "rgba(0,0,0,0.55)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(p.x, p.y, Math.max(3, BALL_R_M * s), 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
}

/** The latest call (serve, point, shot...) as a TV-style pill in the lower-left corner. */
export function drawBanner(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  t: number,
  banners: readonly Banner[],
): void {
  const banner = banners.findLast((b) => b.t <= t && t - b.t < BANNER_S);
  if (!banner) return;
  const age = t - banner.t;
  const fontPx = Math.max(11, Math.min(18, width / 40));
  ctx.font = `600 ${fontPx}px ui-sans-serif, system-ui, sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const textWidth = ctx.measureText(banner.text).width;
  const padX = fontPx * 0.8;
  const h = fontPx * 1.7;
  // Lower-left corner, like a TV graphic: clear of the players at either end.
  const x = padX + textWidth / 2 + width * 0.02;
  const y = height - h / 2 - height * 0.03;
  ctx.globalAlpha = Math.min(1, (BANNER_S - age) / 0.3);
  ctx.fillStyle =
    banner.tone === "out" ? "rgba(159,18,57,0.92)" : banner.tone === "in" ? "rgba(6,95,70,0.92)" : "rgba(9,9,11,0.85)";
  ctx.beginPath();
  ctx.roundRect(x - textWidth / 2 - padX, y - h / 2, textWidth + 2 * padX, h, h / 2);
  ctx.fill();
  ctx.fillStyle = "#fff";
  ctx.fillText(banner.text, x, y + 0.5);
  ctx.globalAlpha = 1;
}
