"use client";

import { ChevronLeft, ChevronRight, Download, Flag, Pause, Play, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { VideoPlayer } from "@/components/live/video-player";
import { Button } from "@/components/ui/button";
import { useSaveLabels } from "@/hooks/queries";
import { api, errorMessage, type MatchLabels } from "@/lib/api";
import { applyKey, formatLabelTime, shortcuts, type Label } from "@/lib/labelling";
import type { Match } from "@/lib/types";

const FRAME_S = 0.04; // one frame at 25 fps
const AUTOSAVE_MS = 800;

/** Watch the match video and mark events with the keyboard; saves automatically. */
export function LabelWorkbench({ match, initial }: { match: Match; initial: MatchLabels }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [labels, setLabels] = useState<Label[]>(initial.events);
  const [until, setUntil] = useState<number | null>(initial.labelled_until_s);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState("Play the video and press a key when something happens.");
  const [now, setNow] = useState(0);
  const [playing, setPlaying] = useState(false);
  const save = useSaveLabels(match.id);
  const sport = match.sport;

  const update = useCallback((next: Label[], note: string) => {
    setLabels(next);
    setDirty(true);
    setMessage(note);
  }, []);

  const seek = useCallback((t: number) => {
    const video = videoRef.current;
    if (video) video.currentTime = Math.max(0, t);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const video = videoRef.current;
      if (!video) return;
      const step = e.shiftKey ? 5 : 1;
      const handled = (() => {
        if (e.key === " ") return (void (video.paused ? video.play() : video.pause()), true);
        if (e.key === "ArrowLeft") return (seek(video.currentTime - step), true);
        if (e.key === "ArrowRight") return (seek(video.currentTime + step), true);
        if (e.key === ",") return (video.pause(), seek(video.currentTime - FRAME_S), true);
        if (e.key === ".") return (video.pause(), seek(video.currentTime + FRAME_S), true);
        const result = applyKey(labels, e.key, video.currentTime, sport);
        if (result) update(result.labels, result.message);
        return result !== null;
      })();
      if (handled) e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [labels, sport, update, seek]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const tick = () => setNow(video.currentTime);
    const play = () => setPlaying(true);
    const pause = () => setPlaying(false);
    video.addEventListener("timeupdate", tick);
    video.addEventListener("seeked", tick);
    video.addEventListener("play", play);
    video.addEventListener("pause", pause);
    return () => {
      video.removeEventListener("timeupdate", tick);
      video.removeEventListener("seeked", tick);
      video.removeEventListener("play", play);
      video.removeEventListener("pause", pause);
    };
  }, []);

  // Autosave shortly after the last change.
  const mutate = save.mutate;
  useEffect(() => {
    if (!dirty) return;
    const timer = window.setTimeout(() => {
      mutate(
        { events: labels, labelled_until_s: until },
        { onSuccess: () => setDirty(false), onError: (error) => setMessage(`Not saved: ${errorMessage(error)}`) },
      );
    }, AUTOSAVE_MS);
    return () => window.clearTimeout(timer);
  }, [dirty, labels, until, mutate]);

  const status = save.isPending ? "Saving…" : dirty ? "Unsaved changes" : "All changes saved";

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section className="flex min-w-0 flex-col gap-3 rounded-lg border bg-card p-3">
        <VideoPlayer sourceType={match.video_source_type} source={match.video_source} videoRef={videoRef} />
        <div className="flex flex-wrap items-center gap-2 px-1">
          <Button size="sm" variant="outline" onClick={() => seek(now - 5)} aria-label="Back 5 seconds">
            −5s
          </Button>
          <Button size="sm" variant="outline" onClick={() => seek(now - FRAME_S)} aria-label="Previous frame">
            <ChevronLeft />
          </Button>
          <Button
            size="sm"
            onClick={() => (videoRef.current?.paused ? videoRef.current?.play() : videoRef.current?.pause())}
            aria-label="Play or pause"
          >
            {playing ? <Pause /> : <Play />}
          </Button>
          <Button size="sm" variant="outline" onClick={() => seek(now + FRAME_S)} aria-label="Next frame">
            <ChevronRight />
          </Button>
          <Button size="sm" variant="outline" onClick={() => seek(now + 5)} aria-label="Forward 5 seconds">
            +5s
          </Button>
          <span className="font-mono text-sm tabular-nums">{formatLabelTime(now)}</span>
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            onClick={() => {
              setUntil(Math.round(now * 100) / 100);
              setDirty(true);
              setMessage(`Labelled up to ${formatLabelTime(now)}`);
            }}
          >
            <Flag /> Labelled up to here
          </Button>
        </div>
        <p role="status" className="px-1 text-sm text-muted-foreground">
          {message}
        </p>
      </section>

      <aside className="flex min-w-0 flex-col gap-4">
        <section className="rounded-lg border bg-card p-4">
          <h2 className="text-sm font-medium">Keys</h2>
          <dl className="mt-2 grid grid-cols-[44px_1fr] gap-x-2 gap-y-1 text-xs">
            {[
              { key: "Space", does: "play / pause" },
              { key: "← →", does: "1 s (Shift: 5 s)" },
              { key: ", .", does: "one frame" },
              ...shortcuts(sport),
            ].map((s) => (
              <div key={s.key + s.does} className="contents">
                <dt className="font-mono text-muted-foreground">{s.key}</dt>
                <dd>{s.does}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="flex min-h-0 flex-col rounded-lg border bg-card">
          <div className="flex items-center justify-between border-b px-4 py-2.5">
            <h2 className="text-sm font-medium">
              Labels <span className="text-muted-foreground">({labels.length})</span>
            </h2>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => window.open(api.labelsExportUrl(match.id), "_blank")}
              aria-label="Download labels (JSON)"
            >
              <Download /> Download
            </Button>
          </div>
          <p className="px-4 py-2 text-xs text-muted-foreground">
            {status}
            {until !== null ? ` · labelled up to ${formatLabelTime(until)}` : ""}
          </p>
          <ul className="max-h-[420px] overflow-y-auto">
            {labels.map((label, i) => (
              <li
                key={`${label.t}-${label.event}-${i}`}
                className="flex items-center gap-2 border-t px-4 py-1.5 text-sm"
              >
                <button
                  type="button"
                  className="font-mono text-xs text-primary tabular-nums hover:underline"
                  onClick={() => seek(label.t)}
                >
                  {formatLabelTime(label.t)}
                </button>
                <span className="font-medium">{label.event.replace("_", " ")}</span>
                <span className="truncate text-xs text-muted-foreground">
                  {Object.entries(label)
                    .filter(([k]) => k !== "t" && k !== "event")
                    .map(([k, v]) => (k === "in" ? (v ? "in" : "out") : String(v)))
                    .join(" · ")}
                </span>
                <Button
                  size="icon-xs"
                  variant="ghost"
                  className="ml-auto"
                  aria-label={`Delete ${label.event} at ${formatLabelTime(label.t)}`}
                  onClick={() =>
                    update(
                      labels.filter((_, j) => j !== i),
                      `Removed ${label.event}`,
                    )
                  }
                >
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        </section>
      </aside>
    </div>
  );
}
