from app.analytics.scoring import ScoreCard


def test_score_is_weighted_and_capped():
    card = ScoreCard(10, 8, 6, 4, 5, 9)
    assert card.overall == 7.05
    assert ScoreCard(12, 12, 12, 12, 12, 12).overall == 10
