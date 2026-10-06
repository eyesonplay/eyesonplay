import { STATUS_LABEL } from "@/lib/format";
import type { MatchStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const TONE: Record<MatchStatus, { text: string; dot: string; ring: string }> = {
  draft: { text: "text-muted-foreground", dot: "bg-muted-foreground/60", ring: "ring-border" },
  ready: { text: "text-sky-300", dot: "bg-sky-400", ring: "ring-sky-400/25" },
  starting: { text: "text-amber-200", dot: "bg-amber-300", ring: "ring-amber-300/25" },
  processing: { text: "text-primary", dot: "bg-primary", ring: "ring-primary/30" },
  paused: { text: "text-amber-200", dot: "bg-amber-300/70", ring: "ring-amber-300/20" },
  completed: { text: "text-zinc-300", dot: "bg-zinc-400", ring: "ring-zinc-400/20" },
  failed: { text: "text-destructive", dot: "bg-destructive", ring: "ring-destructive/30" },
};

export function StatusBadge({ status, className }: { status: MatchStatus; className?: string }) {
  const tone = TONE[status];
  const live = status === "processing" || status === "starting";
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center gap-1.5 rounded-full bg-background/40 px-2 text-[11px] font-medium uppercase tracking-wide ring-1",
        tone.text,
        tone.ring,
        className,
      )}
    >
      <span className="relative flex size-1.5">
        {live ? <span className={cn("absolute inline-flex size-full animate-ping rounded-full opacity-60", tone.dot)} /> : null}
        <span className={cn("relative inline-flex size-1.5 rounded-full", tone.dot)} />
      </span>
      {STATUS_LABEL[status]}
    </span>
  );
}
