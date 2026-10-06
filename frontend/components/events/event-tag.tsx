import { eventLabel, eventTone } from "@/lib/events";
import { cn } from "@/lib/utils";

export function EventTag({ type, className }: { type: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center rounded px-1.5 font-mono text-[10.5px] font-medium tracking-wide ring-1 ring-inset",
        eventTone(type),
        className,
      )}
    >
      {eventLabel(type)}
    </span>
  );
}
