"""Fixed-window counters in Redis (shared by every API replica)."""

from __future__ import annotations

from redis.asyncio import Redis

PREFIX = "ratelimit:"


async def count(redis: Redis, key: str) -> int:
    value = await redis.get(PREFIX + key)
    return int(value) if value else 0


async def hit(redis: Redis, key: str, window_s: int) -> int:
    """Count one more in this window; returns the new count."""
    full = PREFIX + key
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(full)
        pipe.expire(full, window_s, nx=True)
        value, _ = await pipe.execute()
    return int(value)


async def retry_after(redis: Redis, key: str) -> int:
    ttl = await redis.ttl(PREFIX + key)
    return max(int(ttl), 1)


async def reset(redis: Redis, key: str) -> None:
    await redis.delete(PREFIX + key)
