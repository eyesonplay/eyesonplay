/** Pure reducer for a match's low-rate live state: status, metrics, events. */

import type { ConnectionState } from "@/lib/ws";
import type { EventPayload, LiveEnvelope, MatchStatus, MetricsData } from "@/lib/types";

export const EVENT_BUFFER = 2000;

export interface LiveState {
  connection: ConnectionState;
  connectionDetail: string | null;
  status: MatchStatus | null;
  workerStatus: string | null;
  statusMessage: string | null;
  error: string | null;
  metrics: MetricsData | null;
  events: EventPayload[]; // newest first
  eventIds: ReadonlySet<string>;
  lastMessageAt: number | null;
}

export const initialLiveState: LiveState = {
  connection: "connecting",
  connectionDetail: null,
  status: null,
  workerStatus: null,
  statusMessage: null,
  error: null,
  metrics: null,
  events: [],
  eventIds: new Set(),
  lastMessageAt: null,
};

export type LiveAction =
  | { type: "message"; message: LiveEnvelope; receivedAt: number }
  | { type: "connection"; state: ConnectionState; detail?: string }
  | { type: "clear-events" }
  | { type: "reset-session" };

/** Worker session status vocabulary -> match status. */
const WORKER_TO_MATCH: Record<string, MatchStatus> = {
  draft: "draft",
  ready: "ready",
  starting: "starting",
  processing: "processing",
  reconnecting: "processing",
  paused: "paused",
  completed: "completed",
  stopped: "completed",
  failed: "failed",
};

export function toMatchStatus(status: string): MatchStatus | null {
  return WORKER_TO_MATCH[status] ?? null;
}

export function liveReducer(state: LiveState, action: LiveAction): LiveState {
  switch (action.type) {
    case "connection":
      return { ...state, connection: action.state, connectionDetail: action.detail ?? null };
    case "clear-events":
      return { ...state, events: [], eventIds: new Set() };
    case "reset-session":
      return { ...state, metrics: null, events: [], eventIds: new Set(), error: null };
    case "message":
      return applyMessage({ ...state, lastMessageAt: action.receivedAt }, action.message);
  }
}

function applyMessage(state: LiveState, message: LiveEnvelope): LiveState {
  switch (message.type) {
    case "metrics":
      return { ...state, metrics: message.data };
    case "event": {
      const id = message.data.event_id;
      if (state.eventIds.has(id)) return state;
      const events = [message.data, ...state.events].slice(0, EVENT_BUFFER);
      const eventIds = new Set(state.eventIds);
      eventIds.add(id);
      return { ...state, events, eventIds };
    }
    case "status": {
      const status = toMatchStatus(message.data.status);
      const failed = status === "failed";
      return {
        ...state,
        status: status ?? state.status,
        workerStatus: message.data.status,
        statusMessage: message.data.message ?? null,
        error: failed ? (message.data.error ?? message.data.message ?? "Processing failed") : null,
      };
    }
    case "error":
      return { ...state, error: message.data.message };
    case "frame": // high-rate detections live in FrameStore, outside React state
    case "ball":
    case "players":
      return state;
  }
}
