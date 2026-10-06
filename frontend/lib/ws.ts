import { wsBaseUrl } from "@/lib/config";
import type { LiveEnvelope } from "@/lib/types";

export type ConnectionState = "connecting" | "open" | "reconnecting" | "closed";

export interface SocketOptions {
  onMessage: (message: LiveEnvelope) => void;
  onStateChange: (state: ConnectionState, detail?: string) => void;
  /** Called after a reconnect so the caller can reset per-connection state. */
  onReconnect?: () => void;
}

const PING_INTERVAL_MS = 20_000;
const MAX_BACKOFF_MS = 15_000;
const NOT_FOUND_CODE = 4404;

/** WebSocket client for `/ws/matches/{id}` with automatic reconnect (exponential backoff). */
export class MatchSocket {
  private socket: WebSocket | null = null;
  private attempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private closedByClient = false;
  private hasConnected = false;

  constructor(
    private readonly matchId: string,
    private readonly options: SocketOptions,
  ) {}

  connect(): void {
    this.closedByClient = false;
    this.options.onStateChange(this.hasConnected ? "reconnecting" : "connecting");
    const socket = new WebSocket(`${wsBaseUrl()}/ws/matches/${encodeURIComponent(this.matchId)}`);
    this.socket = socket;

    socket.onopen = () => {
      if (this.hasConnected) this.options.onReconnect?.();
      this.hasConnected = true;
      this.attempts = 0;
      this.options.onStateChange("open");
      this.pingTimer = setInterval(() => socket.readyState === WebSocket.OPEN && socket.send("ping"), PING_INTERVAL_MS);
    };
    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        this.options.onMessage(JSON.parse(event.data) as LiveEnvelope);
      } catch {
        // A malformed frame should never take the live view down.
      }
    };
    socket.onclose = (event) => {
      this.clearPing();
      if (this.closedByClient) return;
      if (event.code === NOT_FOUND_CODE) {
        this.options.onStateChange("closed", "Match not found");
        return;
      }
      this.scheduleReconnect();
    };
    socket.onerror = () => socket.close();
  }

  close(): void {
    this.closedByClient = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.clearPing();
    this.socket?.close();
    this.socket = null;
    this.options.onStateChange("closed");
  }

  private scheduleReconnect(): void {
    this.attempts += 1;
    const delay = Math.min(MAX_BACKOFF_MS, 500 * 2 ** (this.attempts - 1)) * (0.8 + Math.random() * 0.4);
    this.options.onStateChange("reconnecting", `Reconnecting in ${Math.ceil(delay / 1000)}s`);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private clearPing(): void {
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.pingTimer = null;
  }
}
