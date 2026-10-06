"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState } from "react";

import { FrameStore } from "@/lib/frame-store";
import { initialLiveState, liveReducer } from "@/lib/live-state";
import { queryKeys } from "@/hooks/queries";
import { MatchSocket } from "@/lib/ws";

const STATUS_REFETCH_DEBOUNCE_MS = 300;
const TERMINAL = new Set(["completed", "stopped", "failed"]);

/**
 * Subscribes to a match's live feed. Low-rate state (status, metrics, events)
 * goes through a reducer; detection frames go to a FrameStore.
 */
export function useMatchSocket(matchId: string) {
  const [state, dispatch] = useReducer(liveReducer, initialLiveState);
  const [frames] = useState(() => new FrameStore());
  const queryClient = useQueryClient();
  const sessionRef = useRef<string | null>(null);

  useEffect(() => {
    let refetchTimer: ReturnType<typeof setTimeout> | null = null;
    const refreshMatch = () => {
      if (refetchTimer) clearTimeout(refetchTimer);
      refetchTimer = setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: queryKeys.match(matchId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.matches });
      }, STATUS_REFETCH_DEBOUNCE_MS);
    };

    const socket = new MatchSocket(matchId, {
      onStateChange: (connection, detail) => dispatch({ type: "connection", state: connection, detail }),
      onReconnect: () => frames.clear(),
      onMessage: (message) => {
        const sid = message.session_id;
        if (sid && sessionRef.current && sid !== sessionRef.current) {
          const startsNewSession =
            message.type === "status" &&
            (message.data.status === "starting" || message.data.origin === "api" || message.data.origin === "snapshot");
          // Late messages from a superseded session (e.g. its final "stopped") are ignored.
          if (!startsNewSession) return;
          frames.clear();
          dispatch({ type: "reset-session" });
        }
        if (sid) sessionRef.current = sid;
        if (message.type === "frame") {
          frames.push(message.data);
          return;
        }
        dispatch({ type: "message", message, receivedAt: Date.now() });
        if (message.type === "status" && TERMINAL.has(message.data.status)) frames.clear(); // no stale overlay
        if (message.type === "status" && message.data.origin !== "snapshot") refreshMatch();
      },
    });
    socket.connect();
    return () => {
      if (refetchTimer) clearTimeout(refetchTimer);
      socket.close();
    };
  }, [matchId, frames, queryClient]);

  return {
    state,
    frames,
    clearEvents: () => dispatch({ type: "clear-events" }),
  };
}
