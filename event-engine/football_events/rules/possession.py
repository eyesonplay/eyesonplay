"""Possession from the nearest player to the ball, with temporal smoothing.

A new holder needs `possession_confirm_frames` consecutive frames as the
nearest player within `possession_radius`. The holder only loses the ball
after `possession_release_frames` consecutive frames outside the larger
`possession_release_radius` (hysteresis), so one noisy frame never changes
possession.
"""

from __future__ import annotations

from dataclasses import replace

from football_events.context import FrameContext, PossessionState
from football_events.geometry import distance, player_position
from football_events.types import EventDraft, EventType, PlayerObservation


class PossessionRule:
    def __init__(self) -> None:
        self._state = PossessionState()
        self._candidate: int | None = None
        self._candidate_frames = 0
        self._away_frames = 0

    @property
    def state(self) -> PossessionState:
        return self._state

    def update(self, ctx: FrameContext) -> tuple[list[EventDraft], PossessionState]:
        # Per-frame flags never carry over to the next frame.
        state = replace(self._state, confirmed=None, released=None)
        ball, pos, space = ctx.ball, ctx.ball_pos, ctx.space
        if ball is None or ball.predicted or pos is None or space is None:
            self._state = state
            return [], state

        cfg = ctx.config
        distances = _player_distances(ctx.obs.players, ctx)
        nearest = min(distances, key=lambda d: d[1], default=None)
        radius = cfg.possession_radius.for_space(space)
        release_radius = cfg.possession_release_radius.for_space(space)

        state = self._update_holder(state, ctx, distances, release_radius)

        in_reach = nearest is not None and nearest[1] <= radius
        if in_reach and nearest is not None and nearest[0].track_id != state.holder:
            return self._update_challenger(state, ctx, nearest, radius)

        self._candidate, self._candidate_frames = None, 0
        self._state = state
        return [], state

    def _update_holder(
        self,
        state: PossessionState,
        ctx: FrameContext,
        distances: list[tuple[PlayerObservation, float]],
        release_radius: float,
    ) -> PossessionState:
        if state.holder is None:
            return state
        holder_dist = next((d for p, d in distances if p.track_id == state.holder), None)
        if holder_dist is not None and holder_dist <= release_radius:
            self._away_frames = 0
            return replace(
                state,
                last_touch_ball=ctx.ball,
                last_touch_time=ctx.t,
                last_touch_frame=ctx.obs.frame_number,
            )
        self._away_frames += 1
        if self._away_frames < ctx.config.possession_release_frames:
            return state
        self._away_frames = 0
        return replace(state, holder=None, holder_confidence=0.0, released=state.holder)

    def _update_challenger(
        self,
        state: PossessionState,
        ctx: FrameContext,
        nearest: tuple[PlayerObservation, float],
        radius: float,
    ) -> tuple[list[EventDraft], PossessionState]:
        player, dist = nearest
        if player.track_id == self._candidate:
            self._candidate_frames += 1
        else:
            self._candidate, self._candidate_frames = player.track_id, 1

        if self._candidate_frames < ctx.config.possession_confirm_frames:
            self._state = state
            return [], state

        ball = ctx.ball
        assert ball is not None  # guarded by caller
        confidence = round(min(0.99, ball.confidence * (1.0 - 0.4 * dist / radius)), 3)
        previous = state.holder if state.holder is not None else state.last_holder
        released = state.released if state.holder is None else state.holder
        new_state = replace(
            state,
            holder=player.track_id,
            holder_confidence=confidence,
            last_holder=player.track_id,
            last_touch_ball=ball,
            last_touch_time=ctx.t,
            last_touch_frame=ctx.obs.frame_number,
            confirmed=player.track_id,
            released=released,
        )
        self._candidate, self._candidate_frames, self._away_frames = None, 0, 0
        self._state = new_state

        drafts = [EventDraft(EventType.POSSESSION, confidence, {"track_id": player.track_id})]
        if previous is not None and previous != player.track_id:
            drafts.append(
                EventDraft(
                    EventType.POSSESSION_CHANGE,
                    confidence,
                    {"from_track_id": previous, "to_track_id": player.track_id},
                )
            )
        return drafts, new_state


def _player_distances(
    players: tuple[PlayerObservation, ...], ctx: FrameContext
) -> list[tuple[PlayerObservation, float]]:
    assert ctx.space is not None and ctx.ball_pos is not None
    result: list[tuple[PlayerObservation, float]] = []
    for player in players:
        if not player.can_possess:
            continue
        pos = player_position(player, ctx.space)
        if pos is not None:
            result.append((player, distance(pos, ctx.ball_pos)))
    return result
