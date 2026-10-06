from worker.detect.bounce_model import bounce_features, load_bounce_scorer


def test_features_follow_the_training_layout():
    window = [(100, 300), (110, 310), (120, 330), (130, 320), (140, 312)]

    f = bounce_features(window)

    assert len(f) == 12
    assert f[0] == 10 and f[1] == 20  # |x(t-1)-x|, |x(t-2)-x|
    assert f[6] == 310 - 330 and f[8] == 320 - 330  # signed y lags (before / after)


def test_missing_model_falls_back_to_rules(tmp_path):
    assert load_bounce_scorer(tmp_path) is None
