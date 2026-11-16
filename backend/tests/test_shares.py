import pytest

from app.shares import equal_shares, make_alias, parse_geos, redistribute


def test_parse_geos_splits_and_dedupes() -> None:
    assert parse_geos("mx, AU;mx RO") == ["MX", "AU", "RO"]


def test_parse_geos_rejects_junk() -> None:
    with pytest.raises(ValueError):
        parse_geos("Mexico")


def test_equal_shares_put_remainder_on_the_last_offers() -> None:
    assert equal_shares(1) == [100]
    assert equal_shares(2) == [50, 50]
    assert equal_shares(3) == [33, 33, 34]
    assert equal_shares(4) == [25, 25, 25, 25]
    assert sum(equal_shares(7)) == 100


def test_redistribute_keeps_pinned_share() -> None:
    offers = [
        {"status": "active", "pinned": True, "share": 25},
        {"status": "active", "pinned": False, "share": 0},
        {"status": "active", "pinned": False, "share": 0},
        {"status": "removed", "pinned": False, "share": 40},
    ]
    redistribute(offers)
    assert [offer["share"] for offer in offers] == [25, 37, 38, 0]


def test_redistribute_rejects_pins_over_100() -> None:
    offers = [
        {"status": "active", "pinned": True, "share": 70},
        {"status": "active", "pinned": True, "share": 50},
    ]
    with pytest.raises(ValueError):
        redistribute(offers)


def test_make_alias_keeps_prefix() -> None:
    assert make_alias("test_plaskin_campaign 1") == "test_plaskin_campaign_1"
