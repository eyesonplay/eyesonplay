"use client";

import { Pencil, Tags } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ErrorState, InlineAlert } from "@/components/common/error-state";
import { StatusBadge } from "@/components/common/status-badge";
import { DetectionOverlay, type OverlayOptions } from "@/components/live/detection-overlay";
import { EventFeed } from "@/components/live/event-feed";
import { JsonInspector } from "@/components/live/json-inspector";
import { MetricsBar } from "@/components/live/metrics-bar";
import { MiniCourt } from "@/components/live/mini-court";
import { MiniPitch } from "@/components/live/mini-pitch";
import { ProcessingControls } from "@/components/live/processing-controls";
import { VideoPlayer } from "@/components/live/video-player";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useMatch } from "@/hooks/queries";
import { useMatchSocket } from "@/hooks/use-match-socket";
import { useVideoPacing } from "@/hooks/use-video-pacing";
import { SOURCE_LABEL, SPORT_LABEL, formatDateTime, formatFixed, modelLabel } from "@/lib/format";
import type { EventPayload, Match } from "@/lib/types";

export default function LiveMatchPage() {
  const { id } = useParams<{ id: string }>();
  const match = useMatch(id);

  if (match.isError) {
    return <ErrorState error={match.error} title="Couldn't load this match" onRetry={() => match.refetch()} />;
  }
  if (!match.data) return <LiveSkeleton />;
  return <LiveView match={match.data} />;
}

function LiveView({ match }: { match: Match }) {
  const { state, frames } = useMatchSocket(match.id);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [selected, setSelected] = useState<EventPayload | null>(null);
  const [overlay, setOverlay] = useState<OverlayOptions>({
    showPlayers: true,
    showTrail: true,
    showLabels: true,
  });

  const status = state.status ?? match.status;
  const tennis = match.sport === "tennis";
  const error = status === "failed" ? (state.error ?? match.last_error) : null;
  const reconnecting = state.workerStatus === "reconnecting";
  const active = status === "starting" || status === "processing" || status === "paused";
  const fps = active ? (state.metrics?.inference_fps ?? match.live?.inference_fps ?? null) : null;
  // Uploaded files and VOD URLs share a clock with the worker; live streams don't.
  const syncToVideo = match.video_source_type === "upload" || match.video_source_type === "url";
  // Keep the player in step with processing for VOD sources: rewind when a
  // session starts, pause and resume with processing.
  const previousStatus = useRef(status);
  useEffect(() => {
    const video = videoRef.current;
    const previous = previousStatus.current;
    previousStatus.current = status;
    if (!video || !syncToVideo || previous === status) return;
    if (status === "processing" && previous !== "paused") {
      video.currentTime = 0;
      void video.play().catch(() => undefined);
    } else if (status === "processing") {
      void video.play().catch(() => undefined);
    } else if (status === "paused") {
      video.pause();
    }
  }, [status, syncToVideo]);
  // The analysis can be slower than real time: keep the picture on the analysed moment.
  useVideoPacing(videoRef, frames, syncToVideo && status === "processing");

  const subtitle = [
    match.competition,
    formatDateTime(match.match_date),
    match.video_source_type && SOURCE_LABEL[match.video_source_type],
    SPORT_LABEL[match.sport],
    modelLabel(match.sport, match.detection_model),
    `${match.processing_fps} fps target`,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="truncate text-lg font-semibold tracking-tight">
              {match.home_team} <span className="text-muted-foreground">vs</span> {match.away_team}
            </h1>
            <StatusBadge status={status} />
            <span className="font-mono text-sm text-muted-foreground tabular-nums">{formatFixed(fps, 1)} FPS</span>
          </div>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{subtitle}</p>
        </div>
        <div className="flex items-center gap-1.5">
          <ProcessingControls matchId={match.id} status={status} hasSource={!!match.video_source} />
          <Button size="sm" variant="ghost" nativeButton={false} render={<Link href={`/matches/${match.id}/label`} />}>
            <Tags /> Label
          </Button>
          <Button
            size="sm"
            variant="ghost"
            nativeButton={false}
            render={<Link href={`/matches/${match.id}/edit`} />}
            aria-label="Edit match"
          >
            <Pencil />
          </Button>
        </div>
      </header>

      {error ? (
        <InlineAlert tone="error" title="Processing failed">
          {error}
        </InlineAlert>
      ) : null}
      {reconnecting ? (
        <InlineAlert tone="warn" title="Source reconnecting">
          {state.statusMessage}
        </InlineAlert>
      ) : null}
      {state.connection === "closed" && state.connectionDetail ? (
        <InlineAlert tone="error" title="Live feed closed">
          {state.connectionDetail}
        </InlineAlert>
      ) : null}
      {!match.video_source ? (
        <InlineAlert tone="info" title="No video source">
          <Link className="underline" href={`/matches/${match.id}/edit`}>
            add a stream URL or upload a video
          </Link>{" "}
          to start processing.
        </InlineAlert>
      ) : null}

      {/* Video and mini court side by side, showing the same moment, for comparison. */}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <section className="min-w-0 rounded-lg border bg-card p-3">
          <VideoPlayer sourceType={match.video_source_type} source={match.video_source} videoRef={videoRef}>
            <DetectionOverlay frames={frames} videoRef={videoRef} syncToVideo={syncToVideo} options={overlay} />
          </VideoPlayer>
          <div className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-2 px-1 text-xs text-muted-foreground">
            <OverlayToggle
              label="Players"
              checked={overlay.showPlayers}
              onChange={(v) => setOverlay({ ...overlay, showPlayers: v })}
            />
            <OverlayToggle
              label="Ball trail"
              checked={overlay.showTrail}
              onChange={(v) => setOverlay({ ...overlay, showTrail: v })}
            />
            <OverlayToggle
              label="Labels"
              checked={overlay.showLabels}
              onChange={(v) => setOverlay({ ...overlay, showLabels: v })}
            />
          </div>
        </section>
        <section className="min-w-0 rounded-lg border bg-card">
          <h2 className="border-b px-4 py-2.5 text-sm font-medium">{tennis ? "Mini court" : "Mini pitch"}</h2>
          <div className="p-3">
            {tennis ? (
              <MiniCourt frames={frames} events={state.events} videoRef={videoRef} syncToVideo={syncToVideo} />
            ) : (
              <MiniPitch frames={frames} events={state.events} videoRef={videoRef} syncToVideo={syncToVideo} />
            )}
          </div>
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="flex h-[440px] min-w-0 flex-col rounded-lg border bg-card" aria-label="Live events">
          <h2 className="flex items-center justify-between border-b px-4 py-2.5 text-sm font-medium">
            Live events
            <span className="font-mono text-xs font-normal text-muted-foreground tabular-nums">
              {state.events.length}
            </span>
          </h2>
          <EventFeed
            events={state.events}
            sport={match.sport}
            selectedId={selected?.event_id ?? null}
            onSelect={setSelected}
          />
        </section>
        <section className="flex h-[440px] min-w-0 flex-col rounded-lg border bg-card" aria-label="JSON inspector">
          <JsonInspector matchId={match.id} events={state.events} selected={selected} />
        </section>
      </div>

      <div className="sticky bottom-3 z-20">
        <MetricsBar metrics={state.metrics} connection={state.connection} connectionDetail={state.connectionDetail} />
      </div>
    </div>
  );
}

function OverlayToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2">
      <Switch size="sm" checked={checked} onCheckedChange={onChange} />
      {label}
    </label>
  );
}

function LiveSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-10 w-80" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="aspect-video" />
        <Skeleton className="aspect-video" />
      </div>
    </div>
  );
}
