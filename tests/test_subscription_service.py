from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionType
from app.models.user import User
from app.services.subscription_service import (
    InvalidPlanAssociationError,
    NoValidSubscriptionError,
    resolve_current_subscription,
)


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


def test_valid_free_subscription_resolves_to_free_plan(db_session):
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

    chosen, plan = resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert chosen.id == sub.id
    assert plan.code == "FREE"


def test_valid_premium_subscription_resolves_to_premium_plan(db_session):
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

    chosen, plan = resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert plan.code == "PREMIUM"
    assert chosen.type == SubscriptionType.PREMIUM


def test_inactive_subscription_not_considered(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="c@example.com", username="c", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.FREE,
        is_active=False,
        start_date=datetime(2025, 11, 30, tzinfo=timezone.utc),
        end_date=None,
    )
    _link_plan(db_session, sub, "FREE", plan_map)

    with pytest.raises(NoValidSubscriptionError):
        resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_expired_subscription_not_considered(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="d@example.com", username="d", hashed_password="h")
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

    with pytest.raises(NoValidSubscriptionError):
        resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_future_start_subscription_not_considered(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="e@example.com", username="e", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.FREE,
        is_active=True,
        start_date=datetime(2026, 2, 1, tzinfo=timezone.utc),
        end_date=None,
    )
    _link_plan(db_session, sub, "FREE", plan_map)

    with pytest.raises(NoValidSubscriptionError):
        resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_no_end_date_current(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="f@example.com", username="f", hashed_password="h")
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

    chosen, plan = resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert plan.code == "PREMIUM"


def test_multiple_valid_resolved_deterministically(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="g@example.com", username="g", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    sub1 = Subscription(
        user_id=user.id,
        type=SubscriptionType.FREE,
        is_active=True,
        start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_date=None,
    )
    sub2 = Subscription(
        user_id=user.id,
        type=SubscriptionType.PREMIUM,
        is_active=True,
        start_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        end_date=None,
    )
    _link_plan(db_session, sub1, "FREE", plan_map)
    _link_plan(db_session, sub2, "PREMIUM", plan_map)

    chosen, plan = resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert chosen.id == sub2.id
    assert plan.code == "PREMIUM"


def test_no_valid_subscription_returns_error(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="h@example.com", username="h", hashed_password="h")
    db_session.add(user)
    db_session.commit()

    with pytest.raises(NoValidSubscriptionError):
        resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_invalid_or_missing_plan_association_raises(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="i@example.com", username="i", hashed_password="h")
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
    # break association
    sub.plan_id = None
    db_session.commit()

    with pytest.raises(InvalidPlanAssociationError):
        resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_utc_aware_and_naive_handled(db_session):
    plan_map = _seed_plans(db_session)
    user = User(email="j@example.com", username="j", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    sub = Subscription(
        user_id=user.id,
        type=SubscriptionType.FREE,
        is_active=True,
        start_date=datetime(2025, 1, 1),  # naive
        end_date=None,
    )
    _link_plan(db_session, sub, "FREE", plan_map)

    chosen, plan = resolve_current_subscription(db_session, user.id, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert chosen.id == sub.id
    assert plan.code == "FREE"
