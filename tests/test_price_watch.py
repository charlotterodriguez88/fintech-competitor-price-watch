from src.price_watch import PriceWatchService


def test_price_change_becomes_a_risk_review():
    review = PriceWatchService.decide("Card plan", 110.0, 100.0)
    monitor = PriceWatchService.decide("Card plan", 102.0, 100.0)

    assert review.decision == "REVIEW"
    assert review.change_ratio == 0.1
    assert monitor.decision == "MONITOR"
