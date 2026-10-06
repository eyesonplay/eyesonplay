"use client";

import { useEffect, useRef, type RefObject } from "react";

import { frameForTime, type FrameStore } from "@/lib/frame-store";
import type { FrameData } from "@/lib/types";

const TRAIL_POINTS = 30;
const SYNC_TOLERANCE_S = 0.5;
const BALL = "#facc15";
const PLAYER = "rgba(125, 211, 252, 0.9)";
const KEEPER = "rgba(249, 115, 22, 0.95)";
const REFEREE = "rgba(244, 114, 182, 0.9)";

export interface OverlayOptions {
  showPlayers: boolean;
  showTrail: boolean;
  showLabels: boolean;
}

interface Viewport {
  scale: number;
  offsetX: number;
  offsetY: number;
}

/** Fit the frame (source pixels) into the element like `object-fit: contain`. */
function viewport(frame: FrameData, width: number, height: number): Viewport {
  const scale = Math.min(width / frame.width, height / frame.height);
  return { scale, offsetX: (width - frame.width * scale) / 2, offsetY: (height - frame.height * scale) / 2 };
}

export function DetectionOverlay({
  frames,
  videoRef,
  syncToVideo,
  options,
}: {
  frames: FrameStore;
  videoRef: RefObject<HTMLVideoElement | null>;
  syncToVideo: boolean;
  options: OverlayOptions;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const optionsRef = useRef(options);
  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    let raf = 0;
    let lastVersion = -1;
    let lastSize = "";
    let lastTime: number | null = null;

    const draw = () => {
      raf = requestAnimationFrame(draw);
      const dpr = window.devicePixelRatio || 1;
      const { clientWidth: w, clientHeight: h } = canvas;
      const size = `${w}x${h}x${dpr}`;
      const video = videoRef.current;
      // Synced sources always follow the video clock, paused or not, so boxes
      // never appear over a different moment than the one on screen.
      const videoTime = syncToVideo && video ? video.currentTime : null;
      const clockMoving = videoTime !== null && video !== null && !video.paused;
      // Redraw only when there is something new (or the video clock moves).
      if (frames.getVersion() === lastVersion && size === lastSize && !clockMoving && videoTime === lastTime) return;
      lastTime = videoTime;
      lastVersion = frames.getVersion();
      if (size !== lastSize) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
        lastSize = size;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const frame = frameForTime(frames.all(), videoTime, SYNC_TOLERANCE_S, videoTime !== null);
      if (frame) render(ctx, frame, viewport(frame, w, h), optionsRef.current);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [frames, videoRef, syncToVideo]);

  return <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 size-full" aria-hidden />;
}

function render(ctx: CanvasRenderingContext2D, frame: FrameData, vp: Viewport, options: OverlayOptions) {
  const px = (x: number) => vp.offsetX + x * vp.scale;
  const py = (y: number) => vp.offsetY + y * vp.scale;
  ctx.font = "500 11px var(--font-geist-mono), ui-monospace, monospace";
  ctx.textBaseline = "bottom";

  if (options.showPlayers) {
    for (const p of frame.players) {
      const [x1, y1, x2, y2] = p.bbox;
      const teamColor = p.team != null ? frame.teams?.find((t) => t.id === p.team)?.color : undefined;
      const color = teamColor ?? (p.class === "goalkeeper" ? KEEPER : p.class === "referee" ? REFEREE : PLAYER);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.25;
      ctx.strokeRect(px(x1), py(y1), (x2 - x1) * vp.scale, (y2 - y1) * vp.scale);
      if (options.showLabels) {
        const label = `${p.track_id != null ? `#${p.track_id} ` : ""}${p.confidence.toFixed(2)}`;
        tag(ctx, label, px(x1), py(y1) - 2, color);
      }
    }
  }

  if (options.showTrail && frame.trail.length > 1) {
    const points = frame.trail.slice(-TRAIL_POINTS);
    for (let i = 1; i < points.length; i++) {
      ctx.strokeStyle = `rgba(250, 204, 21, ${(0.15 + 0.85 * (i / points.length)).toFixed(2)})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(px(points[i - 1].x), py(points[i - 1].y));
      ctx.lineTo(px(points[i].x), py(points[i].y));
      ctx.stroke();
    }
  }

  const ball = frame.ball;
  if (ball) {
    const [x1, y1, x2, y2] = ball.bbox;
    const pad = 4;
    ctx.strokeStyle = BALL;
    ctx.lineWidth = 1.75;
    ctx.setLineDash(ball.predicted ? [3, 3] : []);
    ctx.strokeRect(px(x1) - pad, py(y1) - pad, (x2 - x1) * vp.scale + pad * 2, (y2 - y1) * vp.scale + pad * 2);
    ctx.setLineDash([]);
    ctx.fillStyle = BALL;
    ctx.beginPath();
    ctx.arc(px(ball.pixel.x), py(ball.pixel.y), 2.5, 0, Math.PI * 2);
    ctx.fill();
    if (options.showLabels) {
      tag(ctx, `⚽ ball ${ball.confidence.toFixed(2)}${ball.predicted ? " (predicted)" : ""}`, px(x1) - pad, py(y1) - pad - 2, BALL);
    }
  }
}

function tag(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, color: string) {
  const width = ctx.measureText(text).width + 8;
  ctx.fillStyle = "rgba(9, 11, 15, 0.72)";
  ctx.fillRect(x, y - 15, width, 15);
  ctx.fillStyle = color;
  ctx.fillText(text, x + 4, y - 2);
}
