import numpy as np

from worker.teams.shirt_color import shirt_color
from worker.teams.team_classifier import TeamClassifier, TeamConfig

RED, BLUE, BLACK = np.array([200.0, 40, 40]), np.array([40.0, 70, 200]), np.array([20.0, 20, 20])


def noisy(color, rng, sigma=12.0):
    return np.clip(color + rng.normal(0, sigma, 3), 0, 255)


def frame_players(rng, n=10):
    """Track ids 1-10 wear red, 11-20 blue."""
    return [(i, "player", noisy(RED, rng)) for i in range(1, n + 1)] + [
        (i, "player", noisy(BLUE, rng)) for i in range(n + 1, 2 * n + 1)
    ]


def test_two_kits_are_separated_and_named_by_colour():
    rng = np.random.default_rng(0)
    clf = TeamClassifier()
    for _ in range(5):
        teams = clf.assign(frame_players(rng))

    assert len(set(teams[:10])) == 1 and len(set(teams[10:])) == 1
    assert teams[0] != teams[10] and None not in teams
    colors = {t.id: t.color for t in clf.teams}
    red_team = teams[0]
    assert colors[red_team].startswith("#c") or colors[red_team].startswith("#b")  # reddish


def test_labels_stay_stable_across_refits():
    rng = np.random.default_rng(1)
    clf = TeamClassifier(TeamConfig(refit_every=20))
    first = None
    for _ in range(30):
        teams = clf.assign(frame_players(rng))
        first = first or teams[0]
    assert teams[0] == first


def test_one_bad_frame_does_not_flip_a_player():
    rng = np.random.default_rng(2)
    clf = TeamClassifier()
    for _ in range(6):
        teams = clf.assign(frame_players(rng))
    red_team = teams[0]

    flipped = frame_players(rng)
    flipped[0] = (1, "player", noisy(BLUE, rng))  # track 1 looks blue once
    assert clf.assign(flipped)[0] == red_team


def test_referee_and_off_colour_players_stay_unassigned():
    rng = np.random.default_rng(3)
    clf = TeamClassifier()
    for _ in range(5):
        clf.assign(frame_players(rng))

    teams = clf.assign([(99, "referee", noisy(BLACK, rng)), (98, "player", noisy(BLACK, rng)), (97, "player", None)])

    assert teams == [None, None, None]


def test_no_teams_until_two_distinct_kits_are_seen():
    rng = np.random.default_rng(4)
    clf = TeamClassifier()
    for _ in range(10):
        teams = clf.assign([(i, "player", noisy(RED, rng)) for i in range(1, 11)])
    assert clf.teams == [] and set(teams) == {None}


def test_shirt_color_ignores_grass():
    image = np.zeros((100, 60, 3), np.uint8)
    image[:, :] = (40, 150, 40)  # BGR grass
    image[20:45, 18:42] = (40, 40, 200)  # BGR red torso
    color = shirt_color(image, (0, 0, 60, 100))
    assert color is not None and color[0] > 150 and color[1] < 80  # RGB red


def test_shirt_color_of_tiny_or_all_grass_box_is_none():
    grass = np.full((100, 60, 3), (40, 150, 40), np.uint8)
    assert shirt_color(grass, (0, 0, 60, 100)) is None
    assert shirt_color(grass, (10, 10, 11, 12)) is None
