from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.subscription import Subscription
from app.services.subscription_service import (
    InvalidPlanAssociationError,
    NoValidSubscriptionError,
    resolve_current_subscription,
)


class EntitlementConfigurationError(Exception):
    """Raised when entitlement configuration is invalid."""

    pass


def _get_free_plan(db: Session) -> Plan:
    free_plan = (
        db.query(Plan)
        .filter(Plan.code == "FREE")
        .first()
    )
    if free_plan is None or not free_plan.is_active:
        raise EntitlementConfigurationError("FREE plan is missing or inactive")
    return free_plan


def resolve_effective_entitlement(
    db: Session,
    user_id: int,
    now: Optional[datetime] = None,
) -> Tuple[Plan, Optional[Subscription], bool]:
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        subscription, plan = resolve_current_subscription(db, user_id, now=now)
        return plan, subscription, False
    except NoValidSubscriptionError:
        free_plan = _get_free_plan(db)
        return free_plan, None, True
    except InvalidPlanAssociationError:
        raise
