import type { DetectionModel, MatchStatus, SourceType, Sport } from "@/lib/types";

const numberFormat = new Intl.NumberFormat("en-US");
const dateTimeFormat = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export const formatInt = (value: number | null | undefined) => (value == null ? "—" : numberFormat.format(value));

export function formatFixed(value: number | null | undefined, digits = 1, suffix = ""): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}${suffix}`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFormat.format(date);
}

export function formatRelative(epochSeconds: number, now = Date.now()): string {
  const diff = Math.max(0, Math.round(now / 1000 - epochSeconds));
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function formatVideoTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export const STATUS_LABEL: Record<MatchStatus, string> = {
  draft: "Draft",
  ready: "Ready",
  starting: "Starting",
  processing: "Processing",
  paused: "Paused",
  completed: "Completed",
  failed: "Failed",
};

export const SOURCE_LABEL: Record<SourceType, string> = {
  hls: "Live HLS",
  rtmp: "RTMP",
  url: "Video URL",
  upload: "Uploaded file",
};

export const MODEL_LABEL: Record<DetectionModel, string> = {
  ball: "Ball only",
  ball_players: "Ball + Players",
  ball_players_pitch: "Ball + Players + Pitch",
};

export function sourceSummary(type: SourceType | null, source: string | null): string {
  if (!type || !source) return "No source";
  if (type === "upload") return source.replace(/^uploads\//, "");
  try {
    const url = new URL(source);
    return `${url.host}${url.pathname}`;
  } catch {
    return source;
  }
}

export const SPORT_LABEL: Record<Sport, string> = { football: "Football", tennis: "Tennis" };

/** Detection model names in the sport's own vocabulary (pitch vs court). */
export function modelLabel(sport: Sport, model: DetectionModel): string {
  if (sport === "tennis") {
    return { ball: "Ball only", ball_players: "Ball + Players", ball_players_pitch: "Ball + Players + Court" }[model];
  }
  return MODEL_LABEL[model];
}

export function sideLabels(sport: Sport): { home: string; away: string } {
  return sport === "tennis" ? { home: "Player A", away: "Player B" } : { home: "Home team", away: "Away team" };
}
