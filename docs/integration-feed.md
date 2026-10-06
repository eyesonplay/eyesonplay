# Integration feed

Other systems (a betting or media platform, a club app, a data warehouse) read
matches and live events through the integration feed. It uses API keys, not
dashboard logins.

## API keys

Create a key in the dashboard under **Settings → API keys**. The full key
(`psk_…`) is shown once; only its hash is stored. Revoke it there at any time.
Send it in the `X-API-Key` header (or `?api_key=` where a client cannot set
headers, e.g. a browser WebSocket). Each key may make
`FEED_REQUESTS_PER_MINUTE` requests per minute (default 120); over the limit
the API answers `429` with a `Retry-After` header.

## List matches

```http
GET /api/v1/feed/matches?status=processing&external_ref=riosport:42&limit=100
X-API-Key: psk_…
```

All filters are optional. `status` may repeat. Response:

```json
{
  "data": [
    {
      "id": "match_01m…", "sport": "football", "name": "Arsenal vs Chelsea",
      "home_team": "Arsenal", "away_team": "Chelsea", "competition": "Premier League",
      "match_date": "2026-10-04T15:00:00Z", "status": "processing",
      "external_ref": "riosport:42", "kickoff_offset_seconds": 0.0
    }
  ],
  "error": null, "meta": null
}
```

`external_ref` is your own identifier for the match (set it when creating or
editing the match), so you can link matches without storing EyesOnPlay ids.
Video sources and processing settings are never exposed through the feed.

## Live events

```
wss://<your domain>/ws/v1/feed/matches/{match_id}?api_key=psk_…
```

The same live stream the dashboard uses. On connect you receive a snapshot
(status, latest frame, metrics, recent events), then every message as it
happens:

```json
{ "type": "event", "match_id": "match_01m…", "session_id": "ses_…", "ts": 1760012145.32, "seq": 812, "data": { "event": "corner", "...": "..." } }
```

`type` is one of `status`, `frame`, `ball`, `players`, `event`, `metrics`,
`error`. Event payloads are described in [event-schema.md](event-schema.md).
A missing or revoked key closes the socket with code `4401`; an unknown match
with `4404`. Reconnect with backoff; you get a fresh snapshot each time.

## Example (Python)

```python
import asyncio, json, os
import websockets

async def main():
    url = f"wss://eyes.example.com/ws/v1/feed/matches/{os.environ['MATCH_ID']}?api_key={os.environ['EOP_KEY']}"
    async with websockets.connect(url) as ws:
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "event":
                print(msg["data"]["match_clock"], msg["data"]["event"])

asyncio.run(main())
```
