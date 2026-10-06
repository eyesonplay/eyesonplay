# EyesOnPlay — dashboard

Next.js 16 (App Router) + TypeScript + Tailwind v4 + shadcn/ui (Base UI).

```bash
pnpm install
pnpm dev          # http://localhost:3000, expects the API on <host>:8000
pnpm typecheck && pnpm lint && pnpm test
pnpm test:e2e     # Playwright against a running stack (E2E_BASE_URL to override)
```

- `lib/api.ts`: typed REST client; every response is validated with zod.
- `lib/ws.ts`: reconnecting WebSocket client.
- `lib/live-state.ts`: reducer for status, metrics and events.
- `lib/frame-store.ts`: high-rate detection frames kept outside React state.
- `components/live/*`: video player, canvas overlay, event feed, JSON inspector, mini pitch, metrics bar.
