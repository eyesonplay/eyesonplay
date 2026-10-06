from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.ids import new_id
from app.core.logging import get_logger
from app.core.redis_keys import control_key
from app.db.models import Match, MatchStatus
from app.deps import get_app_settings, get_db, get_redis
from app.repositories.match_repo import MatchRepository
from app.repositories.session_repo import SessionRepository
from app.repositories.settings_repo import SettingsRepository
from app.schemas.common import Envelope, ok
from app.schemas.event import SessionOut
from app.schemas.match import MatchCreate, MatchOut, MatchUpdate
from app.services.realtime import latest_metrics, to_live
from app.services.status_machine import ACTIVE_STATUSES, idle_status

router = APIRouter(prefix="/api/matches", tags=["matches"])
log = get_logger(component="matches")

Db = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]

LOCKED_WHILE_ACTIVE = {
    "sport", "video_source_type", "video_source", "processing_fps", "detection_model", "model_name",
    "confidence_threshold", "enable_event_detection", "enable_player_tracking", "enable_pitch_mapping",
    "kickoff_offset_seconds",
}  # fmt: skip


async def to_out(redis: Redis, matches: list[Match]) -> list[MatchOut]:
    active = [m.id for m in matches if m.status in ACTIVE_STATUSES]
    metrics = await latest_metrics(redis, active)
    return [MatchOut.model_validate(m).model_copy(update={"live": to_live(metrics.get(m.id))}) for m in matches]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Envelope[MatchOut])
async def create_match(body: MatchCreate, db: Db, redis: RedisDep) -> Envelope[MatchOut]:
    defaults = await SettingsRepository(db).get()
    match = Match(
        id=new_id("match"),
        sport=body.sport,
        name=body.name,
        home_team=body.home_team,
        away_team=body.away_team,
        competition=body.competition or None,
        match_date=body.match_date,
        video_source_type=body.video_source_type,
        video_source=body.video_source,
        processing_fps=body.processing_fps or defaults.default_processing_fps,
        detection_model=body.detection_model or defaults.default_detection_model,
        model_name=body.model_name or defaults.default_model_name,
        confidence_threshold=body.confidence_threshold or defaults.default_confidence_threshold,
        enable_event_detection=_or(body.enable_event_detection, defaults.default_enable_event_detection),
        enable_player_tracking=_or(body.enable_player_tracking, defaults.default_enable_player_tracking),
        enable_pitch_mapping=_or(body.enable_pitch_mapping, defaults.default_enable_pitch_mapping),
        kickoff_offset_seconds=body.kickoff_offset_seconds,
        event_count=0,
    )
    match.status = idle_status(match)
    MatchRepository(db).add(match)
    await db.commit()
    await db.refresh(match)
    log.info("match created", match_id=match.id)
    return ok((await to_out(redis, [match]))[0])


def _or(value: bool | None, default: bool) -> bool:
    return default if value is None else value


@router.get("", response_model=Envelope[list[MatchOut]])
async def list_matches(
    db: Db,
    redis: RedisDep,
    status_filter: Annotated[list[MatchStatus] | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Envelope[list[MatchOut]]:
    matches, total = await MatchRepository(db).list(status_filter, q, limit, offset)
    return ok(await to_out(redis, matches), {"total": total, "limit": limit, "offset": offset})


@router.get("/{match_id}", response_model=Envelope[MatchOut])
async def get_match(match_id: str, db: Db, redis: RedisDep) -> Envelope[MatchOut]:
    match = await MatchRepository(db).get_or_404(match_id)
    return ok((await to_out(redis, [match]))[0])


@router.patch("/{match_id}", response_model=Envelope[MatchOut])
async def update_match(match_id: str, body: MatchUpdate, db: Db, redis: RedisDep) -> Envelope[MatchOut]:
    match = await MatchRepository(db).get_or_404(match_id)
    changes = body.model_dump(exclude_unset=True)
    if match.status in ACTIVE_STATUSES and LOCKED_WHILE_ACTIVE & changes.keys():
        raise ConflictError("Stop processing before changing the video source or processing settings")
    for field, value in changes.items():
        setattr(match, field, value)
    # Sources can't change while active, so this only moves idle matches.
    if match.status in (MatchStatus.DRAFT, MatchStatus.READY) or not match.video_source:
        match.status = idle_status(match)
    await db.commit()
    await db.refresh(match)
    return ok((await to_out(redis, [match]))[0])


@router.delete("/{match_id}", status_code=status.HTTP_200_OK, response_model=Envelope[dict])
async def delete_match(match_id: str, request: Request, db: Db, redis: RedisDep) -> Envelope[dict]:
    repo = MatchRepository(db)
    match = await repo.get_or_404(match_id)
    if match.status in ACTIVE_STATUSES:
        raise ConflictError("Stop processing before deleting this match")
    upload = match.video_source if match.video_source_type and match.video_source_type.value == "upload" else None
    await repo.delete(match)
    await db.flush()
    still_used = upload is not None and await repo.count_using_source(upload) > 0
    await db.commit()
    try:
        await redis.delete(control_key(match_id))
    except RedisError as exc:
        log.warning("could not clear control key", match_id=match_id, error=str(exc))
    if upload and not still_used:
        _remove_upload(request, upload)
    log.info("match deleted", match_id=match_id)
    return ok({"id": match_id, "deleted": True})


def _remove_upload(request: Request, relative: str) -> None:
    media_dir = get_app_settings(request).media_dir.resolve()
    path = (media_dir / relative).resolve()
    if media_dir in path.parents:
        path.unlink(missing_ok=True)


@router.get("/{match_id}/sessions", response_model=Envelope[list[SessionOut]])
async def list_sessions(match_id: str, db: Db) -> Envelope[list[SessionOut]]:
    await MatchRepository(db).get_or_404(match_id)
    sessions = await SessionRepository(db).for_match(match_id)
    return ok([SessionOut.model_validate(s) for s in sessions])
