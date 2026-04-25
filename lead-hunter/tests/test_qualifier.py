import pytest
from lead_hunter.models import Business
from lead_hunter.qualifier import QualifyResult, qualify


def biz(**overrides) -> Business:
    defaults = dict(
        name="X", address="Y", phone="+1", website="https://x",
        maps_rating=4.5, maps_reviews=50, permanently_closed=False,
    )
    defaults.update(overrides)
    return Business(**defaults)


def test_closed_always_rejected():
    r = qualify(biz(permanently_closed=True), site_score=5)
    assert r.verdict == "reject"
    assert "closed" in r.reason.lower()


def test_too_few_reviews_rejected():
    r = qualify(biz(maps_reviews=3), site_score=7)
    assert r.verdict == "reject"
    assert "reviews" in r.reason.lower()


def test_rating_too_low_rejected():
    r = qualify(biz(maps_rating=2.5), site_score=7)
    assert r.verdict == "reject"
    assert "rating" in r.reason.lower()


def test_site_already_good_rejected():
    r = qualify(biz(maps_reviews=50, maps_rating=4.8), site_score=1)
    assert r.verdict == "reject"
    assert "already good" in r.reason.lower()


def test_hot_lead():
    r = qualify(biz(maps_reviews=50, maps_rating=4.6), site_score=7)
    assert r.verdict == "qualify"
    assert r.tier == "hot"


def test_warm_lead_mid_score():
    r = qualify(biz(maps_reviews=50, maps_rating=4.6), site_score=4)
    assert r.verdict == "qualify"
    assert r.tier == "warm"


def test_borderline_reviews_exactly_ten_hot():
    r = qualify(biz(maps_reviews=10, maps_rating=3.5), site_score=6)
    assert r.verdict == "qualify"
    assert r.tier == "hot"


def test_rating_just_below_floor_but_above_reject():
    # rating 3.3: not "reject for rating" but not "hot" either (< RATING_MIN)
    # Falls to warm if score in warm range, else reject on site-already-good
    r = qualify(biz(maps_reviews=50, maps_rating=3.3), site_score=7)
    # score ≥ hot but rating < hot threshold → fall to warm tier
    assert r.verdict == "qualify"
    assert r.tier == "warm"
