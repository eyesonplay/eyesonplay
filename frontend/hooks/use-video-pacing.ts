"use client";

import { type RefObject, useEffect } from "react";

import type { FrameStore } from "@/lib/frame-store";
import { RateMeter, pace } from "@/lib/video-pacing";

const TICK_MS = 100;

/**
 * While a synced (uploaded/VOD) source is being processed, keep the video on
 * the analysed moment: it waits (paused) until the analysis has caught up,
 * e.g. while the worker starts, and otherwise plays at the analysis speed.
 * A pause made by the viewer is left alone; normal playback is restored after.
 */
export function useVideoPacing(
  videoRef: RefObject<HTMLVideoElement | null>,
  frames: FrameStore,
  enabled: boolean,
): void {
  useEffect(() => {
    const video = videoRef.current;
    if (!enabled || !video) return;
    const meter = new RateMeter();
    let holding = false; // paused by pacing, not by the viewer

    const hold = () => {
      if (video.paused) return;
      holding = true;
      video.pause();
    };
    const resume = () => {
      if (!holding) return;
      holding = false;
      void video.play().catch(() => undefined);
    };

    const tick = () => {
      const latest = frames.latest();
      if (latest) meter.sample(latest.video_timestamp, performance.now());
      if ((video.paused && !holding) || video.seeking) return; // the viewer paused it
      const decision = pace({
        videoTime: video.currentTime,
        analysedTime: latest?.video_timestamp ?? null,
        analysisRate: meter.rate(),
      });
      if (decision.kind === "hold") {
        hold();
      } else if (decision.kind === "seek") {
        video.currentTime = decision.to;
      } else {
        if (Math.abs(video.playbackRate - decision.rate) > 0.01) video.playbackRate = decision.rate;
        resume();
      }
    };

    tick();
    const timer = window.setInterval(tick, TICK_MS);
    return () => {
      window.clearInterval(timer);
      video.playbackRate = 1;
      resume();
    };
  }, [videoRef, frames, enabled]);
}
