"use client";

import { AlertTriangle, MonitorOff, Pause, Play } from "lucide-react";
import { useEffect, useState, type ReactNode, type RefObject } from "react";

import { mediaUrl } from "@/lib/config";
import type { SourceType } from "@/lib/types";

type PlayerState = "loading" | "playing" | "error" | "unsupported";

/**
 * Plays HLS (hls.js, or native in Safari), MP4 URLs and uploaded files.
 * RTMP cannot be played by browsers; the overlay is drawn on an empty stage.
 */
export function VideoPlayer({
  sourceType,
  source,
  videoRef,
  children,
}: {
  sourceType: SourceType | null;
  source: string | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  children?: ReactNode;
}) {
  const [state, setState] = useState<PlayerState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(true);
  const unsupported = !source || sourceType === "rtmp";

  useEffect(() => {
    const video = videoRef.current;
    if (!video || unsupported || !source) return;
    let destroyed = false;
    let cleanup = () => {};
    const url = sourceType === "upload" ? mediaUrl(source) : source;

    const onError = (message: string) => {
      if (destroyed) return;
      setState("error");
      setError(message);
    };
    const onPlaying = () => {
      setState("playing");
      setPaused(false);
    };
    const onPause = () => setPaused(true);
    const play = () => void video.play().catch(() => setPaused(true)); // autoplay may be blocked: show a play button
    video.addEventListener("playing", onPlaying);
    video.addEventListener("pause", onPause);
    video.addEventListener("canplay", play, { once: true });
    video.addEventListener("error", () => onError("The browser could not play this video."));

    if (sourceType === "hls" && !video.canPlayType("application/vnd.apple.mpegurl")) {
      void import("hls.js").then(({ default: Hls }) => {
        if (destroyed) return;
        if (!Hls.isSupported()) return onError("HLS playback is not supported in this browser.");
        const hls = new Hls({ lowLatencyMode: true, liveSyncDurationCount: 3 });
        hls.on(Hls.Events.ERROR, (_event, data) => {
          if (!data.fatal) return;
          if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
            setError("Stream interrupted — retrying…");
            hls.startLoad();
          } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
            hls.recoverMediaError();
          } else {
            onError(`Stream error: ${data.details}`);
          }
        });
        hls.on(Hls.Events.MANIFEST_PARSED, play);
        hls.loadSource(url);
        hls.attachMedia(video);
        cleanup = () => hls.destroy();
      });
    } else {
      video.src = url;
      play();
      cleanup = () => {
        video.removeAttribute("src");
        video.load();
      };
    }
    return () => {
      destroyed = true;
      video.removeEventListener("playing", onPlaying);
      video.removeEventListener("pause", onPause);
      video.removeEventListener("canplay", play);
      cleanup();
    };
  }, [source, sourceType, unsupported, videoRef]);

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-lg border bg-black">
      {unsupported ? (
        <div className="absolute inset-0 grid place-items-center bg-[radial-gradient(ellipse_at_center,oklch(0.22_0.02_150),oklch(0.12_0.005_255))]">
          <div className="flex flex-col items-center gap-1.5 text-center text-xs text-muted-foreground">
            <MonitorOff className="size-5" />
            {sourceType === "rtmp" ? "RTMP can't be played in the browser — showing detections only" : "No video source"}
          </div>
        </div>
      ) : (
        <video ref={videoRef} className="absolute inset-0 size-full object-contain" muted autoPlay playsInline controls={false} />
      )}
      {children}
      {state === "loading" && !unsupported ? (
        <div className="pointer-events-none absolute top-3 left-3 rounded bg-black/60 px-2 py-1 text-[11px] text-zinc-300">
          Loading video…
        </div>
      ) : null}
      {!unsupported && state !== "error" ? (
        <button
          type="button"
          onClick={() => {
            const video = videoRef.current;
            if (!video) return;
            if (video.paused) void video.play().catch(() => setError("Playback was blocked by the browser."));
            else video.pause();
          }}
          className="absolute bottom-3 left-3 z-10 flex items-center gap-1.5 rounded-md bg-black/65 px-2 py-1 text-[11px] text-zinc-200 backdrop-blur hover:bg-black/80"
          aria-label={paused ? "Play video" : "Pause video"}
        >
          {paused ? <Play className="size-3" /> : <Pause className="size-3" />}
          {paused ? "Play video" : "Pause video"}
        </button>
      ) : null}
      {error ? (
        <div className="absolute inset-x-3 top-3 flex items-center gap-2 rounded-md bg-black/75 px-3 py-2 text-xs text-amber-200">
          <AlertTriangle className="size-3.5 shrink-0" /> {error}
        </div>
      ) : null}
    </div>
  );
}
