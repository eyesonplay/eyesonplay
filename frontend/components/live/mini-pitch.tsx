"use client";

import { MapPinOff } from "lucide-react";
import { type RefObject, useCallback, useMemo, useSyncExternalStore } from "react";

import { drawPitchScene } from "@/components/live/pitch-canvas";
import { type DrawAt, REPLAY_DELAY_S, ReplayCanvas } from "@/components/live/replay-canvas";
import type { FrameStore } from "@/lib/frame-store";
import { KEEPER, REFEREE, activeCorner, footballBanners, pitchSceneAt } from "@/lib/pitch-motion";
import type { CalibrationInfo, EventPayload, FrameData, Point, TeamInfo } from "@/lib/types";

const TRAIL_STEPS = 6;
const TRAIL_STEP_S = 0.06;
const EMPTY_SCENE = { players: [], ball: null, heldFor: null };

function useLatestFrame(store: FrameStore): FrameData | null {
  return useSyncExternalStore(
    store.subscribe,
    () => store.latest(),
    () => null,
  );
}

interface MiniPitchProps {
  frames: FrameStore;
  events: EventPayload[];
  /** Uploaded/VOD sources: follow the video clock so both show the same moment. */
  videoRef?: RefObject<HTMLVideoElement | null>;
  syncToVideo?: boolean;
}

export function MiniPitch({ frames, events, videoRef, syncToVideo = false }: MiniPitchProps) {
  const frame = useLatestFrame(frames);
  const lastCalibrated = frames.latestCalibrated();
  const live = frame?.coordinate_mode === "pitch";
  const teams = frame?.teams ?? lastCalibrated?.teams ?? [];

  return (
    <div>
      {/* Same 16:9 shape as the video beside it; drawn like the main TV camera sees the pitch. */}
      <div
        className="relative aspect-video w-full overflow-hidden rounded-md"
        role="img"
        aria-label="Mini pitch, TV view: players and ball from the live analysis"
      >
        <PitchReplay frames={frames} events={events} videoRef={syncToVideo ? videoRef : undefined} />
        {frame && !live ? (
          <div className="absolute inset-x-0 bottom-2 flex justify-center px-4">
            <div className="flex max-w-md items-start gap-2 rounded-md bg-background/85 px-3 py-2 text-xs text-muted-foreground">
              <MapPinOff className="mt-0.5 size-3.5 shrink-0" />
              <span>{uncalibratedReason(frame.calibration)}</span>
            </div>
          </div>
        ) : null}
        {frame && live ? (
          <div className="absolute top-2 right-2 rounded bg-background/80 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
            {statusLabel(frame.calibration)}
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
      <TeamLegend teams={teams} />
      <p className="mt-1 px-1 text-[11px] text-muted-foreground">
        {syncToVideo ? "In step with the video" : `About ${REPLAY_DELAY_S}s behind the analysis`} · players and ball
        from detections, smoothed between frames · last positions stay faded through close-ups
      </p>
    </div>
  );
}

/** The pitch scene for the moment shown, from the buffered frames. */
function PitchReplay({ frames, events, videoRef }: Omit<MiniPitchProps, "syncToVideo">) {
  const banners = useMemo(() => footballBanners(events), [events]);
  const draw = useCallback<DrawAt>(
    (ctx, w, h, t) => {
      if (t === null) {
        drawPitchScene(ctx, w, h, { t: 0, scene: EMPTY_SCENE, trail: [], banners: [], corner: null });
        return;
      }
      const all = frames.all();
      const scene = pitchSceneAt(all, t);
      const trail: Point[] = [];
      for (let i = 1; scene.ball && i <= TRAIL_STEPS; i += 1) {
        const past = pitchSceneAt(all, t - i * TRAIL_STEP_S).ball;
        if (!past) break;
        trail.push(past);
      }
      drawPitchScene(ctx, w, h, { t, scene, trail, banners, corner: activeCorner(events, t) });
    },
    [frames, events, banners],
  );
  return <ReplayCanvas frames={frames} videoRef={videoRef} draw={draw} />;
}

function statusLabel(calibration: CalibrationInfo | undefined): string {
  if (calibration?.state === "tracking")
    return `following camera · ${Math.round(calibration.age_s ?? 0)}s since landmarks`;
  if (calibration?.state === "ok") return `calibrated · ${calibration.keypoints ?? 0} landmarks`;
  return "calibrated";
}

function TeamLegend({ teams }: { teams: TeamInfo[] }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-xs text-muted-foreground">
      {teams.map((t) => (
        <span key={t.id} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full ring-1 ring-white/40" style={{ background: t.color }} />
          Team {t.label}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full ring-1 ring-white/40" style={{ background: KEEPER }} />
        Goalkeeper
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full ring-1 ring-white/40" style={{ background: REFEREE }} />
        Referee
      </span>
      {teams.length ? <span className="text-[11px]">Teams by shirt colour (home/away unknown)</span> : null}
    </div>
  );
}

/** Why pitch coordinates are unavailable; never guessed. */
export function uncalibratedReason(calibration: CalibrationInfo | undefined): string {
  switch (calibration?.state) {
    case "disabled":
      return "Pitch mapping is off for this match (needs the Ball + Players + Pitch model). Pixel coordinates only.";
    case "no_model":
      return "Pitch keypoint model not installed on the worker (football-pitch-detection.pt). Pixel coordinates only.";
    case "searching":
      if (calibration.pitch_in_view === false)
        return "No pitch in view (graphics, close-up or crowd shot). Pixel coordinates only.";
      return calibration.pending
        ? `Confirming pitch calibration — ${calibration.keypoints ?? 0} landmarks found. Pixel coordinates only.`
        : `Searching for pitch landmarks — ${calibration.keypoints ?? 0} visible, at least 5 well-spread needed. Pixel coordinates only.`;
    default:
      return "Pitch calibration unavailable — pixel coordinates only.";
  }
}
