/**
 * Canvas drawing for the football mini pitch, TV style: the pitch in
 * perspective from the main camera (far touchline at the top), striped
 * grass, all markings, goals with height, standing players in their team
 * colours and the ball with its shadow and a short streak.
 */

import { drawBanner } from "@/components/live/court-canvas";
import { createPerspective, type Projection, type ScreenPoint } from "@/components/live/perspective";
import { type ActiveCorner, CORNER_SHOW_S, type PitchScene } from "@/lib/pitch-motion";
import type { Banner } from "@/lib/rally-path";
import type { Point } from "@/lib/types";

// The normalised 0-100 pitch follows the 120 x 70 m keypoint template.
const LENGTH_M = 120;
const WIDTH_M = 70;
const X = (m: number) => (m / LENGTH_M) * 100;
const Y = (m: number) => (m / WIDTH_M) * 100;
const PENALTY_BOX = { depth: 20.15, width: 41 };
const GOAL_BOX = { depth: 5.5, width: 18.32 };
const GOAL = { width: 7.32, height: 2.44, depth: 2 };
const CIRCLE_R = 9.15;
const SPOT = 11;
const STRIPES = 12;

const FIGURE_SCALE = 2.3; // players drawn larger than life to stay readable
const BODY_H_M = 1.35 * FIGURE_SCALE;
const BODY_W_M = 0.55 * FIGURE_SCALE;
const HEAD_R_M = 0.17 * FIGURE_SCALE;
const BALL_R_M = 0.8; // drawn larger than a real ball (22 cm)
const GRASS_A = "#2f7d3c";
const GRASS_B = "#2a7236";
const LINE = "rgba(255,255,255,0.88)";

export interface PitchFrame {
  t: number;
  scene: PitchScene;
  trail: readonly Point[]; // smoothed ball positions just before t, newest first
  banners: readonly Banner[];
  corner: ActiveCorner | null; // corner flag to highlight (a detected corner)
}

export function createPitchProjection(width: number, height: number): Projection {
  return createPerspective(width, height, {
    // y = 100 is the near touchline (bottom of the picture), y = 0 the far one.
    corners: [
      [-4, 106],
      [104, 106],
      [104, -7],
      [-4, -7],
    ],
    farWidth: 0.62,
    marginTop: 0.1,
    marginBottom: 0.03,
    metre: [100 / LENGTH_M, 0],
  });
}

export function drawPitchScene(ctx: CanvasRenderingContext2D, width: number, height: number, frame: PitchFrame): void {
  const view = createPitchProjection(width, height);
  ctx.clearRect(0, 0, width, height);
  drawGround(ctx, view, width, height);
  drawMarkings(ctx, view);
  drawGoal(ctx, view, 0, -1);
  drawGoal(ctx, view, 100, 1);
  drawCornerFlags(ctx, view, frame.corner);
  ctx.globalAlpha = frame.scene.heldFor !== null ? 0.35 : 1;
  // Far players (small y) first, so nearer ones overlap them.
  for (const p of [...frame.scene.players].sort((a, b) => a.y - b.y)) drawPlayer(ctx, view, p.x, p.y, p.color);
  if (frame.scene.ball) drawBall(ctx, view, frame.scene.ball, frame.trail);
  ctx.globalAlpha = 1;
  drawBanner(ctx, width, height, frame.t, frame.banners);
}

function polygon(ctx: CanvasRenderingContext2D, points: ScreenPoint[]): void {
  ctx.beginPath();
  points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.closePath();
}

function path(ctx: CanvasRenderingContext2D, points: ScreenPoint[]): void {
  ctx.beginPath();
  points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
  ctx.stroke();
}

function rect(view: Projection, x1: number, y1: number, x2: number, y2: number): ScreenPoint[] {
  return [view.point(x1, y1), view.point(x2, y1), view.point(x2, y2), view.point(x1, y2)];
}

function drawGround(ctx: CanvasRenderingContext2D, view: Projection, width: number, height: number): void {
  const sky = ctx.createLinearGradient(0, 0, 0, height);
  sky.addColorStop(0, "#0d1a12");
  sky.addColorStop(1, "#13261a");
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#26662f";
  polygon(ctx, rect(view, -4, -7, 104, 106));
  ctx.fill();
  for (let i = 0; i < STRIPES; i += 1) {
    ctx.fillStyle = i % 2 ? GRASS_A : GRASS_B;
    polygon(ctx, rect(view, (i * 100) / STRIPES, 0, ((i + 1) * 100) / STRIPES, 100));
    ctx.fill();
  }
}

function drawMarkings(ctx: CanvasRenderingContext2D, view: Projection): void {
  ctx.strokeStyle = LINE;
  ctx.lineWidth = Math.max(1, view.scaleAt(50, 50) * 0.18);
  polygon(ctx, rect(view, 0, 0, 100, 100));
  ctx.stroke();
  path(ctx, [view.point(50, 0), view.point(50, 100)]);
  path(ctx, circle(view, 50, 50, CIRCLE_R));
  for (const [goalX, dir] of [
    [0, 1],
    [100, -1],
  ] as const) {
    const box = (depth: number, w: number) =>
      rect(view, goalX, Y((WIDTH_M - w) / 2), goalX + dir * X(depth), Y((WIDTH_M + w) / 2));
    polygon(ctx, box(PENALTY_BOX.depth, PENALTY_BOX.width));
    ctx.stroke();
    polygon(ctx, box(GOAL_BOX.depth, GOAL_BOX.width));
    ctx.stroke();
    const spotX = goalX + dir * X(SPOT);
    ctx.fillStyle = LINE;
    for (const p of [view.point(spotX, 50), view.point(50, 50)]) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, Math.max(1.2, view.scaleAt(50, 50) * 0.25), 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

const CIRCLE_STEPS = 64;

/** Projected circle (radius in metres). */
function circle(view: Projection, cx: number, cy: number, radiusM: number): ScreenPoint[] {
  return Array.from({ length: CIRCLE_STEPS + 1 }, (_, k) => {
    const a = (k / CIRCLE_STEPS) * Math.PI * 2;
    return view.point(cx + X(radiusM) * Math.cos(a), cy + Y(radiusM) * Math.sin(a));
  });
}

/** Goal frame with height and a faint net behind the goal line. */
function drawGoal(ctx: CanvasRenderingContext2D, view: Projection, lineX: number, outward: number): void {
  const y1 = Y((WIDTH_M - GOAL.width) / 2);
  const y2 = Y((WIDTH_M + GOAL.width) / 2);
  const backX = lineX + outward * X(GOAL.depth);
  ctx.fillStyle = "rgba(255,255,255,0.12)";
  polygon(ctx, [
    view.point(lineX, y1, GOAL.height),
    view.point(lineX, y2, GOAL.height),
    view.point(backX, y2, 0),
    view.point(backX, y1, 0),
  ]);
  ctx.fill();
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = Math.max(1.5, view.scaleAt(lineX, 50) * 0.25);
  path(ctx, [
    view.point(lineX, y1),
    view.point(lineX, y1, GOAL.height),
    view.point(lineX, y2, GOAL.height),
    view.point(lineX, y2),
  ]);
}

function drawPlayer(ctx: CanvasRenderingContext2D, view: Projection, x: number, y: number, color: string): void {
  const feet = view.point(x, y);
  const s = view.scaleAt(x, y);
  ctx.fillStyle = "rgba(0,0,0,0.3)";
  ctx.beginPath();
  ctx.ellipse(feet.x + 0.25 * s, feet.y, 0.7 * FIGURE_SCALE * s, 0.25 * FIGURE_SCALE * s, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = color;
  ctx.strokeStyle = "rgba(255,255,255,0.85)";
  ctx.lineWidth = Math.max(0.8, 0.08 * s);
  ctx.beginPath();
  ctx.roundRect(feet.x - (BODY_W_M / 2) * s, feet.y - BODY_H_M * s, BODY_W_M * s, (BODY_H_M - 0.05) * s, 0.25 * s);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(feet.x, feet.y - (BODY_H_M + HEAD_R_M + 0.05) * s, HEAD_R_M * s, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
}

function drawBall(ctx: CanvasRenderingContext2D, view: Projection, ball: Point, trail: readonly Point[]): void {
  const s = view.scaleAt(ball.x, ball.y);
  const base = ctx.globalAlpha;
  // Short streak along the smoothed recent positions.
  ctx.strokeStyle = "#ffffff";
  ctx.lineCap = "round";
  let prev = view.point(ball.x, ball.y);
  trail.forEach((p, i) => {
    const at = view.point(p.x, p.y);
    const fade = 1 - (i + 1) / (trail.length + 1);
    ctx.globalAlpha = base * 0.45 * fade;
    ctx.lineWidth = Math.max(1, BALL_R_M * 1.4 * fade * s);
    ctx.beginPath();
    ctx.moveTo(prev.x, prev.y);
    ctx.lineTo(at.x, at.y);
    ctx.stroke();
    prev = at;
  });
  const p = view.point(ball.x, ball.y);
  ctx.globalAlpha = base * 0.4;
  ctx.fillStyle = "#000";
  ctx.beginPath();
  ctx.ellipse(p.x + 0.3 * s, p.y + 0.1 * s, BALL_R_M * s, BALL_R_M * 0.45 * s, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = base;
  ctx.fillStyle = "#ffffff";
  ctx.strokeStyle = "rgba(0,0,0,0.7)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(p.x, p.y - BALL_R_M * s * 0.6, Math.max(2.5, BALL_R_M * s), 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
}

const FLAG_POLE_M = 1.5 * FIGURE_SCALE;
const FLAG_PULSE_S = 0.8;

/** A small flag on each corner; the one of a detected corner turns yellow and pulses. */
function drawCornerFlags(ctx: CanvasRenderingContext2D, view: Projection, active: ActiveCorner | null): void {
  for (const [x, y] of [
    [0, 0],
    [100, 0],
    [0, 100],
    [100, 100],
  ]) {
    const highlighted = active !== null && active.x === x && active.y === y;
    const s = view.scaleAt(x, y);
    const foot = view.point(x, y);
    if (highlighted) {
      const fade = 1 - active.age / CORNER_SHOW_S;
      const pulse = (active.age % FLAG_PULSE_S) / FLAG_PULSE_S;
      ctx.strokeStyle = `rgba(253,224,71,${0.9 * fade * (1 - pulse)})`;
      ctx.lineWidth = Math.max(1.5, 0.3 * s);
      ctx.beginPath();
      ctx.ellipse(foot.x, foot.y, (2 + 5 * pulse) * s, (0.8 + 2 * pulse) * s, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    const top = view.point(x, y, FLAG_POLE_M);
    ctx.strokeStyle = "rgba(255,255,255,0.9)";
    ctx.lineWidth = Math.max(1, 0.12 * s);
    path(ctx, [foot, top]);
    ctx.fillStyle = highlighted ? "#fde047" : "#f97316";
    const side = x === 0 ? 1 : -1; // flags point into the pitch
    polygon(ctx, [
      top,
      { x: top.x + side * 0.9 * FIGURE_SCALE * s, y: top.y + 0.3 * s },
      { x: top.x, y: top.y + 0.6 * FIGURE_SCALE * s },
    ]);
    ctx.fill();
  }
}
