"use client";

import { Braces, Copy, Download, FileDown, Pause, Play, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/common/empty-state";
import { JsonView } from "@/components/common/json-view";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import type { EventPayload } from "@/lib/types";

const CONSOLE_LIMIT = 150;

function downloadJson(filename: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  link.click();
  URL.revokeObjectURL(url);
}

async function copyJson(value: unknown) {
  try {
    await navigator.clipboard.writeText(JSON.stringify(value, null, 2));
    toast.success("JSON copied to clipboard");
  } catch {
    toast.error("Clipboard is not available in this browser context");
  }
}

export function JsonInspector({
  matchId,
  events,
  selected,
}: {
  matchId: string;
  events: EventPayload[]; // newest first
  selected: EventPayload | null;
}) {
  const [tab, setTab] = useState<"event" | "console">("event");
  const [autoScroll, setAutoScroll] = useState(true);
  const [clearedAt, setClearedAt] = useState(0);
  const consoleRef = useRef<HTMLDivElement>(null);
  const shown = selected ?? events[0] ?? null;

  const consoleEvents = useMemo(
    () => events.filter((e) => e.timestamp > clearedAt).slice(0, CONSOLE_LIMIT).reverse(),
    [events, clearedAt],
  );

  useEffect(() => {
    if (tab === "console" && autoScroll && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [consoleEvents, autoScroll, tab]);

  return (
    <Tabs value={tab} onValueChange={(v) => setTab(v as "event" | "console")} className="flex h-full min-h-0 flex-col gap-0">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-1.5">
        <TabsList variant="line">
          <TabsTrigger value="event">Event</TabsTrigger>
          <TabsTrigger value="console">Console</TabsTrigger>
        </TabsList>
        <div className="flex items-center gap-0.5">
          {tab === "event" ? (
            <>
              <IconButton label="Copy JSON" disabled={!shown} onClick={() => shown && copyJson(shown)}>
                <Copy />
              </IconButton>
              <IconButton label="Download event" disabled={!shown} onClick={() => shown && downloadJson(`${shown.event_id}.json`, shown)}>
                <Download />
              </IconButton>
            </>
          ) : (
            <>
              <IconButton label={autoScroll ? "Pause auto-scroll" : "Resume auto-scroll"} onClick={() => setAutoScroll((v) => !v)}>
                {autoScroll ? <Pause /> : <Play />}
              </IconButton>
              <IconButton
                label="Clear console (view only)"
                onClick={() => {
                  setClearedAt(Date.now() / 1000);
                  toast("Console cleared", { description: "Only this view was cleared; stored events are kept." });
                }}
              >
                <Trash2 />
              </IconButton>
            </>
          )}
          <IconButton label="Download all events (JSON)" onClick={() => window.open(api.exportUrl(matchId), "_blank")}>
            <FileDown />
          </IconButton>
        </div>
      </div>
      <TabsContent value="event" className="relative min-h-0 flex-1">
        {shown ? (
          <div className="scrollbar-thin absolute inset-0 overflow-auto p-3">
            {!selected ? <p className="mb-2 text-[11px] text-muted-foreground">Latest event · click an event to pin it</p> : null}
            <JsonView value={shown} />
          </div>
        ) : (
          <EmptyState icon={Braces} title="No event selected" description="Click an event in the feed to inspect its JSON." />
        )}
      </TabsContent>
      <TabsContent value="console" className="relative min-h-0 flex-1">
        <div ref={consoleRef} className="scrollbar-thin absolute inset-0 overflow-auto bg-black/20 p-3">
          {consoleEvents.length === 0 ? (
            <p className="font-mono text-[11px] text-muted-foreground">› waiting for events…</p>
          ) : (
            consoleEvents.map((e) => (
              <div key={e.event_id} className="border-b border-border/40 py-1.5 last:border-0">
                <JsonView value={e} className="text-[11px]" />
              </div>
            ))
          )}
        </div>
        {!autoScroll ? (
          <span className="absolute right-3 bottom-2 rounded bg-amber-300/15 px-1.5 py-0.5 text-[10px] text-amber-200">
            auto-scroll paused
          </span>
        ) : null}
      </TabsContent>
    </Tabs>
  );
}

function IconButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger render={<Button variant="ghost" size="icon-sm" aria-label={label} disabled={disabled} onClick={onClick} />}>
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
