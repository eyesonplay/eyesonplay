"""Uniform response envelope: `{data, error, meta}`."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    data: T
    error: None = None
    meta: dict[str, Any] | None = None


def ok(data: T, meta: dict[str, Any] | None = None) -> Envelope[T]:
    return Envelope[Any](data=data, meta=meta)  # type: ignore[return-value]
