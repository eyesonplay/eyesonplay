"use client";

import { FileVideo, UploadCloud, X } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { errorMessage, uploadVideo } from "@/lib/api";
import { formatBytes, formatVideoTime } from "@/lib/format";
import type { Upload } from "@/lib/types";
import { cn } from "@/lib/utils";

const ACCEPT = "video/mp4,video/quicktime,video/x-matroska,video/webm,.mp4,.mov,.mkv,.webm";

export function UploadField({
  value,
  onUploaded,
  disabled,
  invalid,
}: {
  value: string;
  onUploaded: (path: string) => void;
  disabled?: boolean;
  invalid?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [uploaded, setUploaded] = useState<Upload | null>(null);
  const [dragging, setDragging] = useState(false);

  const start = async (file: File) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setProgress(0);
    try {
      const result = await uploadVideo(file, setProgress, controller.signal);
      setUploaded(result);
      onUploaded(result.video_source);
      toast.success("Video uploaded", { description: `${result.original_filename} · ${formatBytes(result.size_bytes)}` });
    } catch (error) {
      toast.error("Upload failed", { description: errorMessage(error) });
    } finally {
      setProgress(null);
      abortRef.current = null;
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  if (progress !== null) {
    return (
      <div className="rounded-lg border bg-muted/30 p-4">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span>Uploading… {Math.round(progress * 100)}%</span>
          <Button type="button" variant="ghost" size="xs" onClick={() => abortRef.current?.abort()}>
            <X /> Cancel
          </Button>
        </div>
        <Progress value={progress * 100} />
      </div>
    );
  }

  if (value) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border bg-muted/30 p-3">
        <div className="flex min-w-0 items-center gap-3">
          <FileVideo className="size-5 shrink-0 text-primary" />
          <div className="min-w-0">
            <div className="truncate text-sm">{uploaded?.original_filename ?? value.replace("uploads/", "")}</div>
            {uploaded ? (
              <div className="text-xs text-muted-foreground tabular-nums">
                {formatBytes(uploaded.size_bytes)}
                {uploaded.width ? ` · ${uploaded.width}×${uploaded.height}` : ""}
                {uploaded.duration_s ? ` · ${formatVideoTime(uploaded.duration_s)}` : ""}
              </div>
            ) : null}
          </div>
        </div>
        <Button type="button" variant="outline" size="sm" disabled={disabled} onClick={() => inputRef.current?.click()}>
          Replace
        </Button>
        <input ref={inputRef} type="file" accept={ACCEPT} hidden onChange={(e) => e.target.files?.[0] && start(e.target.files[0])} />
      </div>
    );
  }

  return (
    <>
    <button
      type="button"
      disabled={disabled}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files?.[0];
        if (file) void start(file);
      }}
      className={cn(
        "flex w-full flex-col items-center gap-1.5 rounded-lg border border-dashed px-4 py-7 text-center transition-colors hover:border-primary/40 hover:bg-muted/30 disabled:opacity-50",
        dragging && "border-primary/60 bg-primary/5",
        invalid && "border-destructive/60",
      )}
    >
      <UploadCloud className="size-5 text-muted-foreground" />
      <span className="text-sm">Drop a match video or click to browse</span>
      <span className="text-xs text-muted-foreground">MP4, MOV, MKV or WebM · validated with ffprobe</span>
    </button>
    <input ref={inputRef} type="file" accept={ACCEPT} hidden onChange={(e) => e.target.files?.[0] && start(e.target.files[0])} />
    </>
  );
}
