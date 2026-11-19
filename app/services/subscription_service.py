from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.subscription import Subscription


class InvalidPlanAssociationError(Exception):
    """Raised when a subscription has no valid plan association."""

    pass


class NoValidSubscriptionError(Exception):
    """Raised when a user has no currently valid subscription."""

    pass


def _ensure_utc(dt: datetime) -> datetime:
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_current_subscription(sub: Subscription, now: datetime) -> bool:
    if not sub.is_active:
        return False
    now_utc = _ensure_utc(now)
    start = _ensure_utc(sub.start_date) if sub.start_date is not None else None
    end = _ensure_utc(sub.end_date) if sub.end_date is not None else None
    if start is not None and start > now_utc:
        return False
    if end is not None and end <= now_utc:
        return False
    return True


def resolve_current_subscription(
    db: Session, user_id: int, now: Optional[datetime] = None
) -> Tuple[Subscription, Plan]:
    if now is None:
        now = datetime.now(timezone.utc)

    subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.start_date.desc(), Subscription.id.desc())
        .all()
    )

    candidates = [s for s in subs if _is_current_subscription(s, now)]
    if not candidates:
        raise NoValidSubscriptionError(f"No valid subscription found for user {user_id}")

    chosen = candidates[0]
    if chosen.plan_id is None:
        raise InvalidPlanAssociationError(
            f"Subscription {chosen.id} has no associated plan"
        )
    plan = chosen.plan
    if plan is None:
        raise InvalidPlanAssociationError(
            f"Subscription {chosen.id} has no associated plan"
        )
    return chosen, plan
