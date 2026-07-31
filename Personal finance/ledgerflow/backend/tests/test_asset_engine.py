import uuid
from datetime import date

from app.models.models import Asset, AssetType, AssetValue
from app.services.asset_engine import get_assets_summary


def _make_asset(db_session, user_id, name, asset_type, snapshots):
    """snapshots: list of (value_date, total_value)."""
    asset = Asset(id=uuid.uuid4(), user_id=user_id, name=name, asset_type=asset_type)
    db_session.add(asset)
    db_session.flush()
    for value_date, total_value in snapshots:
        db_session.add(AssetValue(
            id=uuid.uuid4(), user_id=user_id, asset_id=asset.id, value_date=value_date, total_value=total_value,
        ))
    db_session.commit()
    return asset


def test_summary_uses_latest_snapshot_as_current_value(db_session, test_user):
    _make_asset(db_session, test_user.id, "CRDB shares", AssetType.stocks, [
        (date(2026, 1, 1), 1_000_000),
        (date(2026, 3, 1), 1_200_000),
    ])

    summary = get_assets_summary(db_session, test_user.id)
    assert summary["total_value"] == 1_200_000
    assert summary["assets"][0]["current_value"] == 1_200_000
    assert summary["assets"][0]["change_amount"] == 200_000


def test_summary_breaks_down_by_asset_type(db_session, test_user):
    _make_asset(db_session, test_user.id, "CRDB shares", AssetType.stocks, [(date(2026, 1, 1), 1_000_000)])
    _make_asset(db_session, test_user.id, "Treasury bond", AssetType.bonds, [(date(2026, 1, 1), 500_000)])

    summary = get_assets_summary(db_session, test_user.id)
    breakdown = {row["asset_type"]: row["total"] for row in summary["breakdown"]}
    assert breakdown["stocks"] == 1_000_000
    assert breakdown["bonds"] == 500_000
    assert summary["total_value"] == 1_500_000


def test_summary_excludes_inactive_assets(db_session, test_user):
    asset = _make_asset(db_session, test_user.id, "Sold car", AssetType.vehicle, [(date(2026, 1, 1), 20_000_000)])
    asset.is_active = False
    db_session.commit()

    summary = get_assets_summary(db_session, test_user.id)
    assert summary["total_value"] == 0
    assert summary["assets"] == []


def test_summary_excludes_assets_with_no_values(db_session, test_user):
    db_session.add(Asset(id=uuid.uuid4(), user_id=test_user.id, name="Empty asset", asset_type=AssetType.other))
    db_session.commit()

    summary = get_assets_summary(db_session, test_user.id)
    assert summary["assets"] == []


def test_summary_excludes_other_users_assets(db_session, test_user, second_user):
    _make_asset(db_session, second_user.id, "Not mine", AssetType.stocks, [(date(2026, 1, 1), 999_999)])

    summary = get_assets_summary(db_session, test_user.id)
    assert summary["total_value"] == 0
    assert summary["assets"] == []


def test_trend_forward_fills_across_staggered_snapshot_dates(db_session, test_user):
    _make_asset(db_session, test_user.id, "Asset A", AssetType.stocks, [
        (date(2026, 1, 1), 100),
        (date(2026, 3, 1), 150),
    ])
    _make_asset(db_session, test_user.id, "Asset B", AssetType.bonds, [
        (date(2026, 2, 1), 200),
    ])

    summary = get_assets_summary(db_session, test_user.id)
    trend = {row["date"]: row["total_value"] for row in summary["trend"]}

    # Before Asset B's first snapshot, only Asset A counts.
    assert trend["2026-01-01"] == 100
    # Once Asset B has a value, it's forward-filled into the total.
    assert trend["2026-02-01"] == 300
    # Asset A's later snapshot updates the running total.
    assert trend["2026-03-01"] == 350
