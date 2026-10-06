from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnprocessableError
from app.deps import get_db
from app.repositories.event_repo import EventRepository
from app.repositories.match_repo import MatchRepository
from app.schemas.common import Envelope, ok
from app.schemas.event import EVENT_GROUPS, EventOut

router = APIRouter(tags=["events"])
Db = Annotated[AsyncSession, Depends(get_db)]
Types = Annotated[list[str] | None, Query(alias="type", description="Event type, repeatable")]
Groups = Annotated[list[str] | None, Query(alias="group", description="ball|pass|shot|possession|out|goal")]
Limit = Annotated[int, Query(ge=1, le=500)]


def resolve_types(types: list[str] | None, groups: list[str] | None) -> list[str] | None:
    resolved = set(types or [])
    for group in groups or []:
        if group not in EVENT_GROUPS:
            raise UnprocessableError(f"Unknown event group '{group}'", details=sorted(EVENT_GROUPS))
        resolved.update(EVENT_GROUPS[group])
    return sorted(resolved) or None


def _page(events: list, limit: int) -> dict:
    return {"limit": limit, "next_before_id": events[-1].id if len(events) == limit else None}


@router.get("/api/matches/{match_id}/events", response_model=Envelope[list[EventOut]])
async def match_events(
    match_id: str,
    db: Db,
    types: Types = None,
    groups: Groups = None,
    limit: Limit = 100,
    before_id: Annotated[int | None, Query(ge=1)] = None,
) -> Envelope[list[EventOut]]:
    await MatchRepository(db).get_or_404(match_id)
    events = await EventRepository(db).list(match_id, resolve_types(types, groups), limit, before_id)
    return ok([EventOut.model_validate(e) for e in events], _page(events, limit))


@router.get("/api/events", response_model=Envelope[list[EventOut]])
async def all_events(
    db: Db,
    match_id: str | None = None,
    types: Types = None,
    groups: Groups = None,
    limit: Limit = 100,
    before_id: Annotated[int | None, Query(ge=1)] = None,
) -> Envelope[list[EventOut]]:
    events = await EventRepository(db).list(match_id, resolve_types(types, groups), limit, before_id)
    return ok([EventOut.model_validate(e) for e in events], _page(events, limit))


@router.get("/api/matches/{match_id}/events/export")
async def export_events(match_id: str, db: Db) -> StreamingResponse:
    """All events of a match as a downloadable JSON array, streamed in chunks."""
    match = await MatchRepository(db).get_or_404(match_id)
    repo = EventRepository(db)

    async def body() -> AsyncIterator[str]:
        yield "["
        first = True
        async for payload in repo.stream_payloads(match.id):
            yield ("" if first else ",") + "\n  " + json.dumps(payload, separators=(",", ":"))
            first = False
        yield "\n]\n"

    filename = f"{match.id}-events.json"
    return StreamingResponse(
        body(), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
