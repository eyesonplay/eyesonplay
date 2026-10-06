"""Goals: confirmed by the broadcast scoreboard, timed by the goal moment."""

from dataclasses import replace

from football_events import EventEngine
from football_events.types import ScoreboardObservation

from conftest import FPS, frames, hold, of_type, run, travel

PLAYERS = {9: (80, 50)}


def with_score(observations, home, away, *, first_read, reads_every=10, banner=False):
    """Attach scoreboard readings: a new read every `reads_every` frames."""
    out = []
    for i, obs in enumerate(observations):
        read = first_read + i // reads_every
        out.append(replace(obs, scoreboard=ScoreboardObservation(read, home, away, banner)))
    return out


def stretch(seconds, start, ball=(50, 50)):
    return frames(hold(ball, PLAYERS, int(seconds * FPS)), start=start)


def test_a_score_change_read_twice_is_a_goal():
    obs = with_score(stretch(3, 0), 0, 0, first_read=0) + with_score(stretch(3, 30), 1, 0, first_read=3)

    goals = of_type(run(EventEngine("m1"), obs), "goal")

    assert len(goals) == 1
    assert goals[0].details["team"] == "home"
    assert goals[0].details["score"] == {"home": 1, "away": 0}
    assert "scoreboard" in goals[0].details["evidence"]


def test_the_opening_score_is_not_a_goal():
    obs = with_score(stretch(3, 0), 2, 1, first_read=0)  # highlights start at 2-1

    assert of_type(run(EventEngine("m1"), obs), "goal") == []


def test_a_single_misread_is_ignored():
    obs = (
        with_score(stretch(2, 0), 1, 0, first_read=0)
        + with_score(stretch(1, 20), 1, 1, first_read=2)  # one bad read
        + with_score(stretch(3, 30), 1, 0, first_read=3)
    )

    assert of_type(run(EventEngine("m1"), obs), "goal") == []


def test_the_goal_is_timed_at_the_goal_graphic():
    obs = (
        with_score(stretch(3, 0), 0, 0, first_read=0)
        + with_score(stretch(2, 30), 0, 0, first_read=3, banner=True)  # "GOAL" shown from 3.0 s
        + with_score(stretch(3, 50), 0, 1, first_read=5)
    )

    goals = of_type(run(EventEngine("m1"), obs), "goal")

    assert len(goals) == 1 and goals[0].details["team"] == "away"
    assert goals[0].video_timestamp == 3.0
    assert set(goals[0].details["evidence"]) == {"scoreboard", "goal_graphic"}


def test_the_goal_is_timed_when_the_ball_crosses_the_line_between_the_posts():
    shot = frames(
        hold((90, 50), PLAYERS, 5) + travel((90, 50), (101.5, 49), PLAYERS, 4) + hold((101.5, 49), PLAYERS, 10),
        start=30,
    )
    obs = (
        with_score(stretch(3, 0), 0, 0, first_read=0)
        + with_score(shot, 0, 0, first_read=3)
        + with_score(stretch(3, 60), 1, 0, first_read=10)
    )

    events = run(EventEngine("m1"), obs)

    candidates, goals = of_type(events, "goal_candidate"), of_type(events, "goal")
    assert len(candidates) == 1
    assert len(goals) == 1 and "ball_in_goal" in goals[0].details["evidence"]
    assert goals[0].video_timestamp == candidates[0].video_timestamp


def test_a_lower_score_is_not_a_goal_and_becomes_the_new_baseline():
    obs = (
        with_score(stretch(3, 0), 2, 1, first_read=0)
        + with_score(stretch(3, 30), 1, 1, first_read=3)  # e.g. VAR or a misread pair
        + with_score(stretch(3, 60), 2, 1, first_read=6)
    )

    goals = of_type(run(EventEngine("m1"), obs), "goal")

    assert [g.details["score"] for g in goals] == [{"home": 2, "away": 1}]


def test_a_jump_of_two_reports_both_goals():
    obs = with_score(stretch(3, 0), 1, 1, first_read=0) + with_score(stretch(3, 30), 3, 1, first_read=3)

    goals = of_type(run(EventEngine("m1"), obs), "goal")

    assert [g.details["score"] for g in goals] == [{"home": 2, "away": 1}, {"home": 3, "away": 1}]
    assert all(g.confidence < 0.9 for g in goals)  # the goal moments were not seen


def test_without_a_scoreboard_the_ball_in_goal_is_only_a_candidate():
    shot = frames(hold((90, 50), PLAYERS, 5) + travel((90, 50), (101.5, 49), PLAYERS, 4) + hold((101.5, 49), PLAYERS, 10))

    events = run(EventEngine("m1"), shot)

    assert len(of_type(events, "goal_candidate")) == 1
    assert of_type(events, "goal") == []


def test_a_ball_wide_of_the_posts_is_not_a_candidate():
    wide = frames(hold((90, 20), PLAYERS, 5) + travel((90, 20), (101.5, 15), PLAYERS, 4) + hold((101.5, 15), PLAYERS, 10))

    assert of_type(run(EventEngine("m1"), wide), "goal_candidate") == []
