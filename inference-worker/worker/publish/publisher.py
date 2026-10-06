"""Publishes worker output to Redis using the shared envelope
`{type, match_id, session_id, ts, seq, data}` (see docs/redis-contract.md)."""

from __future__ import annotations

import itertools
import json
import time
from typing import Any

from redis.asyncio import Redis

from worker.control.commands import EVENTS_STREAM, STATUS_STREAM, channel
from worker.pipeline import FrameResult

LAST_STATE_TTL_S = 30
STATE_TTL_S = 3600
STREAM_MAXLEN = 200_000


class Publisher:
    def __init__(self, redis: Redis, match_id: str, session_id: str, worker_id: str, device: str) -> None:
        self._redis = redis
        self._match_id = match_id
        self._session_id = session_id
        self._worker_id = worker_id
        self._device = device
        self._seq = itertools.count(1)

    def envelope(self, kind: str, data: Any) -> str:
        return json.dumps(
            {
                "type": kind,
                "match_id": self._match_id,
                "session_id": self._session_id,
                "ts": round(time.time(), 3),
                "seq": next(self._seq),
                "data": data,
            },
            separators=(",", ":"),
        )

    async def frame(self, result: FrameResult) -> None:
        frame_env = self.envelope("frame", result.frame_message())
        pipe = self._redis.pipeline(transaction=False)
        pipe.publish(channel(self._match_id, "detections"), frame_env)
        pipe.set(channel(self._match_id, "frame:last"), frame_env, ex=LAST_STATE_TTL_S)
        for event in result.events:
            event_env = self.envelope("event", event.to_payload())
            pipe.publish(channel(self._match_id, "events"), event_env)
            pipe.xadd(EVENTS_STREAM, {"payload": event_env}, maxlen=STREAM_MAXLEN, approximate=True)
        await pipe.execute()

    async def metrics(self, snapshot: dict[str, Any]) -> None:
        env = self.envelope("metrics", snapshot)
        pipe = self._redis.pipeline(transaction=False)
        pipe.publish(channel(self._match_id, "metrics"), env)
        pipe.set(channel(self._match_id, "metrics:last"), env, ex=LAST_STATE_TTL_S)
        await pipe.execute()

    async def status(self, status: str, message: str | None = None, stats: dict[str, Any] | None = None) -> None:
        data = {
            "status": status,
            "message": message,
            "worker_id": self._worker_id,
            "device": self._device,
            "stats": stats,
        }
        env = self.envelope("status", data)
        pipe = self._redis.pipeline(transaction=False)
        pipe.publish(channel(self._match_id, "status"), env)
        pipe.set(channel(self._match_id, "state"), env, ex=STATE_TTL_S)
        pipe.xadd(STATUS_STREAM, {"payload": env}, maxlen=STREAM_MAXLEN, approximate=True)
        await pipe.execute()

    async def error(self, message: str) -> None:
        await self._redis.publish(channel(self._match_id, "status"), self.envelope("error", {"message": message}))
