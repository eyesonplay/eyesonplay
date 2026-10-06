"use client";

import { type RefObject, useEffect, useRef } from "react";

import type { FrameStore } from "@/lib/frame-store";

// Without a synced video the view runs this far behind the newest analysed
// frame, so what happened around the moment shown has arrived.
export const REPLAY_DELAY_S = 1.0;
const MAX_EXTRAPOLATION_S = 0.5; // never run ahead of the analysis by more than this

/** Draws the view for video time t (null before any frame has arrived). */
export type DrawAt = (ctx: CanvasRenderingContext2D, width: number, height: number, t: number | null) => void;

/**
 * Animation loop shared by the mini court and mini pitch: redraws every
 * display frame at the video's time for uploaded/VOD sources, otherwise at a
 * smooth clock following the analysis.
 */
export function ReplayCanvas({
  frames,
  videoRef,
  draw,
}: {
  frames: FrameStore;
  videoRef?: RefObject<HTMLVideoElement | null>;
  draw: DrawAt;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawRef = useRef(draw);
  useEffect(() => {
    drawRef.current = draw;
  }, [draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const clock = new AnalysisClock();
    let raf = 0;
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      const latest = frames.latest();
      const video = videoRef?.current;
      const t =
        video && video.readyState > 0
          ? video.currentTime
          : latest
            ? clock.at(latest.video_timestamp, now) - REPLAY_DELAY_S
            : null;
      const dpr = window.devicePixelRatio || 1;
      const { clientWidth: w, clientHeight: h } = canvas;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawRef.current(ctx, w, h, t);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [frames, videoRef]);

  return <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 size-full" aria-hidden />;
}

/**
 * Smooth video time that advances at the rate frames are being analysed
 * (slower than real time when the worker cannot keep up), so the view never
 * jumps ahead of the data.
 */
class AnalysisClock {
  private lastTs: number | null = null;
  private lastWall = 0;
  private rate = 1;
  private shown: number | null = null;

  at(latestTs: number, now: number): number {
    if (this.lastTs === null || latestTs < this.lastTs - 1) {
      this.reset(latestTs, now); // first frame, or a new session started over
    } else if (latestTs !== this.lastTs) {
      const elapsed = (now - this.lastWall) / 1000;
      if (elapsed > 0)
        this.rate = 0.9 * this.rate + 0.1 * Math.min(2, Math.max(0.05, (latestTs - this.lastTs) / elapsed));
      this.lastTs = latestTs;
      this.lastWall = now;
    }
    const target = this.lastTs! + Math.min(MAX_EXTRAPOLATION_S, (this.rate * (now - this.lastWall)) / 1000);
    this.shown =
      this.shown === null || Math.abs(target - this.shown) > 2 ? target : this.shown + (target - this.shown) * 0.2;
    return this.shown;
  }

  private reset(ts: number, now: number): void {
    this.lastTs = ts;
    this.lastWall = now;
    this.rate = 1;
    this.shown = null;
  }
}
