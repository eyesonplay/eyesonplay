import { z } from "zod";

import type { MatchInput } from "@/lib/api";
import { DETECTION_MODELS, SOURCE_TYPES, SPORTS, type AppSettings, type Match } from "@/lib/types";

const CLOCK = /^(\d{1,3}):([0-5]\d)$/;
const UPLOAD = /^uploads\/[a-z0-9]{26}\.(mp4|mov|mkv|webm)$/;

export const matchFormSchema = z
  .object({
    sport: z.enum(SPORTS),
    name: z.string().trim().min(1, "Match name is required").max(200),
    home_team: z.string().trim().min(1, "Home team is required").max(120),
    away_team: z.string().trim().min(1, "Away team is required").max(120),
    competition: z.string().trim().max(120),
    match_date: z.string().min(1, "Match date is required"),
    video_source_type: z.enum(SOURCE_TYPES),
    video_source: z.string().trim().max(2048),
    processing_fps: z.number().int(),
    detection_model: z.enum(DETECTION_MODELS),
    model_name: z.string().regex(/^[A-Za-z0-9._-]{1,120}$/, "Letters, digits, dot, dash and underscore only"),
    confidence_threshold: z.number().min(0.05).max(0.99),
    enable_event_detection: z.boolean(),
    enable_player_tracking: z.boolean(),
    enable_pitch_mapping: z.boolean(),
    kickoff_clock: z.string().regex(CLOCK, "Use mm:ss, e.g. 45:00"),
  })
  .superRefine((value, ctx) => {
    const source = value.video_source;
    if (!source) return; // no source yet: the match is saved as a draft
    const issue = (message: string) => ctx.addIssue({ code: "custom", path: ["video_source"], message });
    if (value.video_source_type === "upload") {
      if (!UPLOAD.test(source)) issue("Upload a video file first");
      return;
    }
    const lower = source.toLowerCase();
    if (value.video_source_type === "rtmp") {
      if (!lower.startsWith("rtmp://") && !lower.startsWith("rtmps://")) issue("RTMP URLs start with rtmp:// or rtmps://");
      return;
    }
    if (!lower.startsWith("http://") && !lower.startsWith("https://")) issue("URL must start with http:// or https://");
  });

export type MatchFormValues = z.infer<typeof matchFormSchema>;

function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function clockToSeconds(clock: string): number {
  const match = CLOCK.exec(clock);
  return match ? Number(match[1]) * 60 + Number(match[2]) : 0;
}

export function secondsToClock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function defaultValues(settings?: AppSettings): MatchFormValues {
  return {
    sport: "football",
    name: "",
    home_team: "",
    away_team: "",
    competition: "",
    match_date: toLocalInput(new Date()),
    video_source_type: "hls",
    video_source: "",
    processing_fps: settings?.default_processing_fps ?? 10,
    detection_model: settings?.default_detection_model ?? "ball_players_pitch",
    model_name: settings?.default_model_name ?? "yolov8n",
    confidence_threshold: settings?.default_confidence_threshold ?? 0.5,
    enable_event_detection: settings?.default_enable_event_detection ?? true,
    enable_player_tracking: settings?.default_enable_player_tracking ?? true,
    enable_pitch_mapping: settings?.default_enable_pitch_mapping ?? true,
    kickoff_clock: "00:00",
  };
}

export function valuesFromMatch(match: Match): MatchFormValues {
  return {
    sport: match.sport,
    name: match.name,
    home_team: match.home_team,
    away_team: match.away_team,
    competition: match.competition ?? "",
    match_date: toLocalInput(new Date(match.match_date)),
    video_source_type: match.video_source_type ?? "hls",
    video_source: match.video_source ?? "",
    processing_fps: match.processing_fps,
    detection_model: match.detection_model,
    model_name: match.model_name,
    confidence_threshold: match.confidence_threshold,
    enable_event_detection: match.enable_event_detection,
    enable_player_tracking: match.enable_player_tracking,
    enable_pitch_mapping: match.enable_pitch_mapping,
    kickoff_clock: secondsToClock(match.kickoff_offset_seconds),
  };
}

export function toMatchInput(values: MatchFormValues): MatchInput {
  const hasSource = values.video_source.length > 0;
  const tracksPlayers = values.detection_model !== "ball";
  return {
    sport: values.sport,
    name: values.name,
    home_team: values.home_team,
    away_team: values.away_team,
    competition: values.competition || null,
    match_date: new Date(values.match_date).toISOString(),
    video_source_type: hasSource ? values.video_source_type : null,
    video_source: hasSource ? values.video_source : null,
    processing_fps: values.processing_fps,
    detection_model: values.detection_model,
    model_name: values.model_name,
    confidence_threshold: Math.round(values.confidence_threshold * 100) / 100,
    enable_event_detection: values.enable_event_detection,
    enable_player_tracking: tracksPlayers && values.enable_player_tracking,
    enable_pitch_mapping: values.detection_model === "ball_players_pitch" && values.enable_pitch_mapping,
    kickoff_offset_seconds: clockToSeconds(values.kickoff_clock),
  };
}
