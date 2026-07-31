import uuid
from datetime import date

from app.models.models import Asset, AssetType, AssetValue, Liability, LiabilityType, LiabilityValue
from app.services.liability_engine import get_liabilities_summary, get_net_worth_trend


def _make_liability(db_session, user_id, name, liability_type, snapshots):
    """snapshots: list of (value_date, total_value)."""
    liability = Liability(id=uuid.uuid4(), user_id=user_id, name=name, liability_type=liability_type)
    db_session.add(liability)
    db_session.flush()
    for value_date, total_value in snapshots:
        db_session.add(LiabilityValue(
            id=uuid.uuid4(), user_id=user_id, liability_id=liability.id, value_date=value_date, total_value=total_value,
        ))
    db_session.commit()
    return liability


def _make_asset(db_session, user_id, name, asset_type, snapshots):
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
    _make_liability(db_session, test_user.id, "NMB Car Loan", LiabilityType.loan, [
        (date(2026, 1, 1), 5_000_000),
        (date(2026, 3, 1), 4_200_000),
    ])

    summary = get_liabilities_summary(db_session, test_user.id)
    assert summary["total_value"] == 4_200_000
    assert summary["liabilities"][0]["current_value"] == 4_200_000
    assert summary["liabilities"][0]["change_amount"] == -800_000


def test_summary_breaks_down_by_liability_type(db_session, test_user):
    _make_liability(db_session, test_user.id, "NMB Car Loan", LiabilityType.loan, [(date(2026, 1, 1), 4_000_000)])
    _make_liability(db_session, test_user.id, "Visa Card", LiabilityType.credit_card, [(date(2026, 1, 1), 500_000)])

    summary = get_liabilities_summary(db_session, test_user.id)
    breakdown = {row["liability_type"]: row["total"] for row in summary["breakdown"]}
    assert breakdown["loan"] == 4_000_000
    assert breakdown["credit_card"] == 500_000
    assert summary["total_value"] == 4_500_000


def test_summary_excludes_inactive_liabilities(db_session, test_user):
    liability = _make_liability(db_session, test_user.id, "Paid off loan", LiabilityType.loan, [(date(2026, 1, 1), 1_000_000)])
    liability.is_active = False
    db_session.commit()

    summary = get_liabilities_summary(db_session, test_user.id)
    assert summary["total_value"] == 0
    assert summary["liabilities"] == []


def test_summary_excludes_liabilities_with_no_values(db_session, test_user):
    db_session.add(Liability(id=uuid.uuid4(), user_id=test_user.id, name="Empty liability", liability_type=LiabilityType.other))
    db_session.commit()

    summary = get_liabilities_summary(db_session, test_user.id)
    assert summary["liabilities"] == []


def test_summary_excludes_other_users_liabilities(db_session, test_user, second_user):
    _make_liability(db_session, second_user.id, "Not mine", LiabilityType.loan, [(date(2026, 1, 1), 999_999)])

    summary = get_liabilities_summary(db_session, test_user.id)
    assert summary["total_value"] == 0
    assert summary["liabilities"] == []


def test_trend_forward_fills_across_staggered_snapshot_dates(db_session, test_user):
    _make_liability(db_session, test_user.id, "Loan A", LiabilityType.loan, [
        (date(2026, 1, 1), 1000),
        (date(2026, 3, 1), 800),
    ])
    _make_liability(db_session, test_user.id, "Card B", LiabilityType.credit_card, [
        (date(2026, 2, 1), 200),
    ])

    summary = get_liabilities_summary(db_session, test_user.id)
    trend = {row["date"]: row["total_value"] for row in summary["trend"]}

    assert trend["2026-01-01"] == 1000
    assert trend["2026-02-01"] == 1200
    assert trend["2026-03-01"] == 1000


def test_net_worth_trend_combines_assets_and_liabilities(db_session, test_user):
    _make_asset(db_session, test_user.id, "Shares", AssetType.stocks, [
        (date(2026, 1, 1), 1_000_000),
        (date(2026, 3, 1), 1_200_000),
    ])
    _make_liability(db_session, test_user.id, "Loan", LiabilityType.loan, [
        (date(2026, 2, 1), 300_000),
    ])

    trend = {row["date"]: row["net_worth"] for row in get_net_worth_trend(db_session, test_user.id)}

    assert trend["2026-01-01"] == 1_000_000
    assert trend["2026-02-01"] == 700_000
    assert trend["2026-03-01"] == 900_000


def test_net_worth_trend_empty_when_nothing_tracked(db_session, test_user):
    assert get_net_worth_trend(db_session, test_user.id) == []
