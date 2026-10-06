"use client";

import { MapPinOff } from "lucide-react";
import { type RefObject, useCallback, useMemo, useSyncExternalStore } from "react";

import { PLAYER_COLORS, drawScene } from "@/components/live/court-canvas";
import { type DrawAt, REPLAY_DELAY_S, ReplayCanvas } from "@/components/live/replay-canvas";
import { frameForTime, type FrameStore } from "@/lib/frame-store";
import { buildBanners, buildKeyframes, playersAt } from "@/lib/rally-path";
import type { CalibrationInfo, EventPayload, FrameData } from "@/lib/types";

const PLAYER_STALE_S = 1.0;

function useLatestFrame(store: FrameStore): FrameData | null {
  return useSyncExternalStore(
    store.subscribe,
    () => store.latest(),
    () => null,
  );
}

interface MiniCourtProps {
  frames: FrameStore;
  events: EventPayload[];
  /** Uploaded/VOD sources: follow the video clock so both show the same moment. */
  videoRef?: RefObject<HTMLVideoElement | null>;
  syncToVideo?: boolean;
}

export function MiniCourt({ frames, events, videoRef, syncToVideo = false }: MiniCourtProps) {
  const frame = useLatestFrame(frames);
  const calibrated = frame?.coordinate_mode === "pitch";

  return (
    <div>
      {/* Same 16:9 shape as the video beside it; drawn like the TV camera sees the court. */}
      <div
        className="relative aspect-video w-full overflow-hidden rounded-md"
        role="img"
        aria-label="Mini tennis court, TV view: replay of detected shots, bounces and player positions"
      >
        <CourtReplay frames={frames} events={events} videoRef={syncToVideo ? videoRef : undefined} />
        {frame && !calibrated ? (
          <div className="absolute inset-x-0 bottom-2 flex justify-center px-4">
            <div className="flex max-w-md items-start gap-2 rounded-md bg-background/85 px-3 py-2 text-xs text-muted-foreground">
              <MapPinOff className="mt-0.5 size-3.5 shrink-0" />
              <span>{courtReason(frame.calibration)}</span>
            </div>
          </div>
        ) : null}
        {!frame ? (
          <div className="absolute inset-x-0 bottom-3 flex justify-center">
            <span className="rounded-md bg-background/85 px-3 py-1.5 text-xs text-muted-foreground">
              Waiting for detections
            </span>
          </div>
        ) : null}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-xs text-muted-foreground">
        <Legend color={PLAYER_COLORS.near} label="Near player (bottom)" />
        <Legend color={PLAYER_COLORS.far} label="Far player (top)" />
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-3 rounded-full bg-emerald-400" /> Bounce in
        </span>
        <span className="flex items-center gap-1.5 text-rose-300">✕ Bounce out</span>
        <span className="text-[11px]">
          {syncToVideo ? "In step with the video" : `About ${REPLAY_DELAY_S}s behind the analysis`} · ball path from
          detected hits and bounces · height is drawn, not measured
        </span>
      </div>
    </div>
  );
}

/** The court scene for the moment shown: rally path from events, players from frames. */
function CourtReplay({ frames, events, videoRef }: Omit<MiniCourtProps, "syncToVideo">) {
  const banners = useMemo(() => buildBanners(events), [events]);
  // Hits need the buffered frames around them, which exist once the event arrives.
  const keys = useMemo(() => buildKeyframes(events, frames.all()), [events, frames]);
  const draw = useCallback<DrawAt>(
    (ctx, w, h, t) => {
      if (t === null) {
        drawScene(ctx, w, h, { t: 0, keys: [], banners: [], players: { near: null, far: null }, dimmed: false });
        return;
      }
      const all = frames.all();
      const atT = frameForTime(all, t, PLAYER_STALE_S, true);
      const located = atT?.coordinate_mode === "pitch";
      drawScene(ctx, w, h, {
        t,
        keys,
        banners,
        players: located ? playersAt(all, t) : { near: null, far: null },
        dimmed: atT !== null && !located,
      });
    },
    [frames, keys, banners],
  );
  return <ReplayCanvas frames={frames} videoRef={videoRef} draw={draw} />;
}

/** Why court coordinates are unavailable right now; never guessed. */
export function courtReason(calibration: CalibrationInfo | undefined): string {
  if (calibration?.state === "no_court" || calibration?.pitch_in_view === false) {
    return "Court not in view (close-up, replay or crowd shot). Finding it again as soon as the wide camera is back.";
  }
  if (calibration?.state === "searching") return "Looking for the court lines…";
  if (calibration?.state === "disabled") return "Court mapping is off for this match. Pixel coordinates only.";
  return "Court calibration unavailable — pixel coordinates only.";
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="size-2.5 rounded-full ring-1 ring-white/40" style={{ background: color }} />
      {label}
    </span>
  );
}
