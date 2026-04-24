from lead_hunter.dedup import filter_new
from lead_hunter.models import Business


def biz(name, website=None, phone=None):
    return Business(
        name=name, address="x", phone=phone, website=website,
        maps_rating=4.0, maps_reviews=20, permanently_closed=False,
    )


def test_filter_new_removes_website_duplicates():
    existing = {"website:https://a.com"}
    incoming = [biz("A", website="https://a.com"), biz("B", website="https://b.com")]
    result = filter_new(incoming, existing)
    assert [b.name for b in result] == ["B"]


def test_filter_new_removes_phone_duplicates():
    existing = {"phone:+15551111"}
    incoming = [biz("A", phone="+15551111"), biz("B", phone="+15552222")]
    assert [b.name for b in filter_new(incoming, existing)] == ["B"]


def test_filter_new_removes_if_any_key_matches():
    existing = {"phone:+15551111"}
    incoming = [biz("A", website="https://new.com", phone="+15551111")]
    assert filter_new(incoming, existing) == []


def test_filter_new_keeps_business_with_neither_key_matching():
    existing = {"website:https://x.com", "phone:+19999"}
    incoming = [biz("A", website="https://y.com", phone="+18888")]
    assert [b.name for b in filter_new(incoming, existing)] == ["A"]


def test_filter_new_dedups_within_incoming_batch():
    existing: set[str] = set()
    incoming = [
        biz("A", website="https://a.com", phone="+1"),
        biz("A-dup", website="https://a.com", phone="+2"),  # same website → dupe
    ]
    result = filter_new(incoming, existing)
    assert [b.name for b in result] == ["A"]


def test_filter_new_keeps_businesses_with_no_dedup_keys():
    # Business with neither website nor phone has empty dedup_keys — always "new"
    existing: set[str] = set()
    incoming = [biz("Ghost")]
    assert [b.name for b in filter_new(incoming, existing)] == ["Ghost"]
