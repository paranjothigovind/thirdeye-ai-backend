from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionType
from app.models.user import User
from app.services.entitlement_service import (
    EntitlementConfigurationError,
    resolve_effective_entitlement,
)
from app.services.subscription_service import InvalidPlanAssociationError


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_plans(db):
    plans = [
        Plan(code="FREE", name="Free"),
        Plan(code="PREMIUM", name="Premium"),
        Plan(code="ENTERPRISE", name="Enterprise"),
    ]
    db.add_all(plans)
    db.commit()
    return {p.code: p for p in db.query(Plan).all()}


def _link_plan(db, sub, code, plan_map):
    sub.plan_id = plan_map[code].id
    db.add(sub)
    db.commit()
    db.refresh(sub)


def test_valid_free_subscription(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="a@example.com", username="a", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.FREE,
        is_active=True,
        start_date=datetime(2025, 11, 30, tzinfo=timezone.utc),
        end_date=None,
    )
    _link_plan(db_session, sub, "FREE", plan_map)

    plan, subscription, used_free_fallback = resolve_effective_entitlement(
        db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    assert plan.code == "FREE"
    assert subscription is not None
    assert subscription.id == sub.id
    assert used_free_fallback is False


def test_valid_premium_subscription(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="b@example.com", username="b", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.PREMIUM,
        is_active=True,
        start_date=datetime(2025, 11, 30, tzinfo=timezone.utc),
        end_date=None,
    )
    _link_plan(db_session, sub, "PREMIUM", plan_map)

    plan, subscription, used_free_fallback = resolve_effective_entitlement(
        db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    assert plan.code == "PREMIUM"
    assert subscription is not None
    assert used_free_fallback is False


def test_expired_premium_falls_back_to_free(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="c@example.com", username="c", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.PREMIUM,
        is_active=True,
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )
    _link_plan(db_session, sub, "PREMIUM", plan_map)

    plan, subscription, used_free_fallback = resolve_effective_entitlement(
        db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    assert plan.code == "FREE"
    assert subscription is None
    assert used_free_fallback is True


def test_inactive_premium_falls_back_to_free(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="d@example.com", username="d", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.PREMIUM,
        is_active=False,
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=None,
    )
    _link_plan(db_session, sub, "PREMIUM", plan_map)

    plan, subscription, used_free_fallback = resolve_effective_entitlement(
        db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    assert plan.code == "FREE"
    assert subscription is None
    assert used_free_fallback is True


def test_no_subscription_falls_back_to_free(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="e@example.com", username="e", hashed_password="h")
    db_session.add(user)
    db_session.commit()

    plan, subscription, used_free_fallback = resolve_effective_entitlement(
        db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    assert plan.code == "FREE"
    assert subscription is None
    assert used_free_fallback is True


def test_missing_or_inactive_free_plan_raises(db_session):
    plans = [
        Plan(code="PREMIUM", name="Premium"),
        Plan(code="ENTERPRISE", name="Enterprise"),
    ]
    db_session.add_all(plans)
    db_session.commit()
    user = User(email="f@example.com", username="f", hashed_password="h")
    db_session.add(user)
    db_session.commit()

    with pytest.raises(EntitlementConfigurationError):
        resolve_effective_entitlement(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_inactive_free_plan_raises(db_session):
    plan_map = _seed_plans(db_session)
    free_plan = plan_map["FREE"]
    free_plan.is_active = False
    db_session.add(free_plan)
    db_session.commit()
    user = User(email="g@example.com", username="g", hashed_password="h")
    db_session.add(user)
    db_session.commit()

    with pytest.raises(EntitlementConfigurationError):
        resolve_effective_entitlement(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_invalid_plan_association_does_not_fall_back(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="h@example.com", username="h", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.PREMIUM,
        is_active=True,
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=None,
    )
    _link_plan(db_session, sub, "PREMIUM", plan_map)
    sub.plan_id = None
    db_session.commit()

    with pytest.raises(InvalidPlanAssociationError):
        resolve_effective_entitlement(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_historical_subscriptions_remain_unchanged(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="i@example.com", username="i", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    expired = Subscription(
        user_id=user.id,
        type=SubscriptionType.PREMIUM,
        is_active=True,
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )
    _link_plan(db_session, expired, "PREMIUM", plan_map)
    count_before = db_session.query(Subscription).count()
    plan, subscription, used_free_fallback = resolve_effective_entitlement(
        db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    count_after = db_session.query(Subscription).count()
    assert count_before == count_after
    assert plan.code == "FREE"
    assert subscription is None
    assert used_free_fallback is True
