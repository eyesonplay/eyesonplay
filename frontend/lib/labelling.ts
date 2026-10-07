/**
 * Keyboard labelling of match videos: one key marks an event at the current
 * video time; detail keys tag the label just marked. Labels are the benchmark
 * and training format ({t, event, ...details}). Pure functions, never mutating.
 */

import type { Sport } from "@/lib/types";

export type LabelValue = string | number | boolean | null;
export type Label = { t: number; event: string } & Record<string, LabelValue>;

export interface KeyResult {
  labels: Label[];
  message: string;
}

interface Detail {
  name: string; // shown in the help
  apply: (event: string) => Record<string, LabelValue> | null; // null: not for this event
}

const EVENT_KEYS: Record<Sport, Record<string, string>> = {
  tennis: { s: "serve", h: "hit", b: "bounce", f: "fault", p: "point_won" },
  football: { g: "goal", c: "corner", s: "shot", o: "ball_out", p: "pass" },
};

const side =
  (value: string): Detail["apply"] =>
  (event): Record<string, LabelValue> | null => {
    if (event === "point_won") return { winner: value };
    return ["serve", "hit", "fault"].includes(event) ? { player: value } : null;
  };
const team =
  (value: string): Detail["apply"] =>
  (event) =>
    ["goal", "shot", "corner", "pass"].includes(event) ? { team: value } : null;
const bounce =
  (value: boolean): Detail["apply"] =>
  (event) =>
    event === "bounce" ? { in: value } : null;

const DETAIL_KEYS: Record<Sport, Record<string, Detail>> = {
  tennis: {
    "1": { name: "near player", apply: side("near") },
    "2": { name: "far player", apply: side("far") },
    i: { name: "bounce in", apply: bounce(true) },
    o: { name: "bounce out", apply: bounce(false) },
  },
  football: {
    "1": { name: "home team", apply: team("home") },
    "2": { name: "away team", apply: team("away") },
  },
};

const RECENT_S = 3; // detail and delete keys act on a label marked this recently

/** Shortcut list for the help panel. */
export function shortcuts(sport: Sport): { key: string; does: string }[] {
  return [
    ...Object.entries(EVENT_KEYS[sport]).map(([key, event]) => ({
      key: key.toUpperCase(),
      does: event.replace("_", " "),
    })),
    ...Object.entries(DETAIL_KEYS[sport]).map(([key, d]) => ({ key: key.toUpperCase(), does: `tag: ${d.name}` })),
    { key: "⌫", does: "delete the label just marked" },
  ];
}

export function applyKey(labels: readonly Label[], key: string, t: number, sport: Sport): KeyResult | null {
  if (key === "Backspace") return remove(labels, t);
  const lower = key.toLowerCase();
  const event = EVENT_KEYS[sport][lower];
  if (event) {
    const label: Label = { t: Math.round(t * 100) / 100, event };
    return { labels: [...labels, label].sort((a, b) => a.t - b.t), message: `${event} at ${formatLabelTime(label.t)}` };
  }
  const detail = DETAIL_KEYS[sport][lower];
  return detail ? tag(labels, detail, t) : null;
}

function recentIndex(labels: readonly Label[], t: number): number {
  let best = -1;
  labels.forEach((label, i) => {
    if (label.t <= t + 0.01 && t - label.t <= RECENT_S && (best === -1 || label.t >= labels[best].t)) best = i;
  });
  return best;
}

function tag(labels: readonly Label[], detail: Detail, t: number): KeyResult {
  const i = recentIndex(labels, t);
  const update = i === -1 ? null : detail.apply(labels[i].event);
  if (i === -1 || update === null) return { labels: [...labels], message: `Nothing to tag as ${detail.name} here` };
  const tagged: Label = { ...labels[i], ...update };
  return { labels: labels.map((l, j) => (j === i ? tagged : l)), message: `${tagged.event}: ${detail.name}` };
}

function remove(labels: readonly Label[], t: number): KeyResult {
  const i = recentIndex(labels, t);
  if (i === -1) return { labels: [...labels], message: "No label just before this moment" };
  return {
    labels: labels.filter((_, j) => j !== i),
    message: `Removed ${labels[i].event} at ${formatLabelTime(labels[i].t)}`,
  };
}

export function formatLabelTime(t: number): string {
  const minutes = Math.floor(t / 60);
  const seconds = t - minutes * 60;
  return `${minutes}:${seconds.toFixed(2).padStart(5, "0")}`;
}
