/** Event taxonomy shared by the live feed, filters and the events browser. */

import type { Sport } from "@/lib/types";

export type EventFilter =
  | "all" | "ball" | "pass" | "shot" | "possession" | "out" | "corner" | "goal"
  | "serve" | "hit" | "bounce" | "point"; // prettier-ignore

export interface FilterOption {
  key: EventFilter;
  label: string;
}

export const FOOTBALL_FILTERS: FilterOption[] = [
  { key: "all", label: "All" },
  { key: "ball", label: "Ball" },
  { key: "pass", label: "Pass" },
  { key: "shot", label: "Shot" },
  { key: "possession", label: "Possession" },
  { key: "out", label: "Out" },
  { key: "corner", label: "Corner" },
  { key: "goal", label: "Goal" },
];

export const TENNIS_FILTERS: FilterOption[] = [
  { key: "all", label: "All" },
  { key: "serve", label: "Serve" },
  { key: "hit", label: "Hit" },
  { key: "bounce", label: "Bounce" },
  { key: "out", label: "Out" },
  { key: "point", label: "Point" },
];

/** Every filter, for views that mix sports (the Events page). */
export const EVENT_FILTERS: FilterOption[] = [
  ...FOOTBALL_FILTERS,
  ...TENNIS_FILTERS.filter((t) => !FOOTBALL_FILTERS.some((f) => f.key === t.key)),
];

export function filtersFor(sport: Sport): FilterOption[] {
  return sport === "tennis" ? TENNIS_FILTERS : FOOTBALL_FILTERS;
}

const GROUP_OF: Record<string, Exclude<EventFilter, "all">> = {
  ball_detected: "ball",
  ball_lost: "ball",
  ball_move: "ball",
  pass: "pass",
  pass_candidate: "pass",
  shot: "shot",
  shot_candidate: "shot",
  possession: "possession",
  possession_change: "possession",
  ball_out: "out",
  corner: "corner",
  goal: "goal",
  serve: "serve",
  fault: "serve",
  double_fault: "serve",
  hit: "hit",
  bounce: "bounce",
  point_won: "point",
};

export function eventGroup(type: string): EventFilter | null {
  return GROUP_OF[type] ?? null;
}

export function matchesFilter(type: string, filter: EventFilter): boolean {
  return filter === "all" || eventGroup(type) === filter;
}

export function eventLabel(type: string): string {
  return type.replaceAll("_", " ").toUpperCase();
}

/** Tailwind classes for the small type tag in feeds and tables. */
export function eventTone(type: string): string {
  switch (eventGroup(type)) {
    case "pass":
      return "text-sky-300 bg-sky-400/10 ring-sky-400/20";
    case "shot":
      return "text-rose-300 bg-rose-400/10 ring-rose-400/20";
    case "possession":
      return "text-amber-200 bg-amber-300/10 ring-amber-300/20";
    case "out":
      return "text-violet-300 bg-violet-400/10 ring-violet-400/20";
    case "corner":
      return "text-yellow-200 bg-yellow-300/10 ring-yellow-300/20";
    case "goal":
    case "point":
      return "text-emerald-300 bg-emerald-400/10 ring-emerald-400/20";
    case "serve":
      return "text-sky-300 bg-sky-400/10 ring-sky-400/20";
    case "hit":
      return "text-amber-200 bg-amber-300/10 ring-amber-300/20";
    case "bounce":
      return "text-zinc-300 bg-zinc-300/10 ring-zinc-300/15";
    default:
      return "text-zinc-400 bg-zinc-400/10 ring-zinc-400/15";
  }
}

/** One-line human summary of an event payload. Never invents identities. */
export function eventSummary(payload: Record<string, unknown>): string {
  const n = (k: string) => (typeof payload[k] === "number" ? (payload[k] as number) : null);
  const distance = n("distance");
  switch (payload.event) {
    case "pass":
      return `#${n("from_track_id")} → #${n("to_track_id")}${distance != null ? ` · ${distance.toFixed(1)}${payload.distance_unit ?? ""}` : ""}`;
    case "pass_candidate":
      return `from #${n("from_track_id")}`;
    case "possession":
      return `track #${n("track_id")}`;
    case "possession_change":
      return `#${n("from_track_id")} → #${n("to_track_id")}`;
    case "shot":
    case "shot_candidate":
      return payload.target_goal
        ? `#${n("track_id")} → ${payload.target_goal} goal`
        : `#${n("track_id")} · speed spike`;
    case "ball_out":
      return `${payload.side ?? ""} line`;
    case "corner":
      return `${String(payload.corner ?? "").replace("_", " ")}${n("taker_track_id") != null ? ` · taker #${n("taker_track_id")}` : ""}`;
    case "ball_lost":
      return `missing ${n("missing_frames")} frames`;
    // tennis
    case "serve":
      return `${payload.player} · serve ${n("serve_number") ?? 1}${payload.court ? ` · ${payload.court} court` : ""}`;
    case "hit":
      return `${payload.player} · ${payload.side ?? ""} side · shot ${n("rally_hits") ?? ""}`;
    case "bounce":
      return payload.in === true
        ? `IN · ${payload.side ?? ""}`
        : payload.in === false
          ? `OUT · ${payload.side ?? ""}`
          : "no court calibration";
    case "fault":
    case "double_fault":
      return `${payload.player}`;
    case "point_won":
      return `${payload.winner} wins · ${String(payload.reason ?? "").replaceAll("_", " ")} · rally ${n("rally_length") ?? 0}`;
    default:
      return "";
  }
}
