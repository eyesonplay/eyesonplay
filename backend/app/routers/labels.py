"""Hand-labelled ground truth per match (the dashboard's labelling page)."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MatchLabels
from app.deps import get_db
from app.repositories.match_repo import MatchRepository
from app.schemas.common import Envelope, ok
from app.schemas.labels import LabelsIn, LabelsOut

router = APIRouter(prefix="/api/matches/{match_id}/labels", tags=["labels"])
Db = Annotated[AsyncSession, Depends(get_db)]


def _out(row: MatchLabels | None) -> LabelsOut:
    if row is None:
        return LabelsOut(events=[], labelled_until_s=None, updated_at=None)
    return LabelsOut(events=row.events, labelled_until_s=row.labelled_until_s, updated_at=row.updated_at)


@router.get("", response_model=Envelope[LabelsOut])
async def get_labels(match_id: str, db: Db) -> Envelope[LabelsOut]:
    await MatchRepository(db).get_or_404(match_id)
    return ok(_out(await db.get(MatchLabels, match_id)))


@router.put("", response_model=Envelope[LabelsOut])
async def save_labels(match_id: str, body: LabelsIn, db: Db) -> Envelope[LabelsOut]:
    await MatchRepository(db).get_or_404(match_id)
    events = sorted((e.model_dump() for e in body.events), key=lambda e: e["t"])
    row = await db.get(MatchLabels, match_id)
    if row is None:
        row = MatchLabels(match_id=match_id)
        db.add(row)
    row.events = events
    row.labelled_until_s = body.labelled_until_s
    await db.commit()
    await db.refresh(row)
    return ok(_out(row))


@router.get("/export")
async def export_labels(match_id: str, db: Db) -> Response:
    """The labels as a benchmark/training file (python -m eop_benchmark LABELS EVENTS)."""
    match = await MatchRepository(db).get_or_404(match_id)
    row = await db.get(MatchLabels, match_id)
    document = {
        "sport": match.sport.value,
        "source": f"{match.name} ({match.id}), labelled in EyesOnPlay",
        "labelled_until_s": row.labelled_until_s if row else None,
        "events": row.events if row else [],
    }
    return Response(
        json.dumps(document, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{match.id}-labels.json"'},
    )
