"""LMS course payments via Razorpay Standard Checkout.

Amount, currency and user are always derived server-side. Enrollment is activated only
after a captured payment is confirmed with Razorpay's server API (verify) or a
signature-checked webhook; "authorized" and "failed" payments never unlock anything.
"""
import json
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.course import Course, CourseEnrollment
from app.models.payment import Payment
from app.models.user import User
from app.schemas.lms_payment import (
    CreateOrderRequest,
    CreateOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from app.services import razorpay_client
from app.services.razorpay_client import RazorpayError

router = APIRouter()
logger = get_logger(__name__)


def _require_configured() -> None:
    if not razorpay_client.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Payments are not available right now")


def _activate_enrollment(db: Session, payment: Payment) -> None:
    """Create or reactivate the buyer's enrollment (idempotent, race-safe)."""
    def existing():
        return (db.query(CourseEnrollment)
                .filter(CourseEnrollment.user_id == payment.user_id,
                        CourseEnrollment.course_id == payment.course_id).first())

    enrollment = existing()
    if enrollment is None:
        try:
            with db.begin_nested():
                db.add(CourseEnrollment(user_id=payment.user_id, course_id=payment.course_id,
                                        status="active", enrolled_at=datetime.now(timezone.utc)))
        except IntegrityError:
            enrollment = existing()  # a concurrent request created it
    if enrollment is not None and enrollment.status != "active":
        enrollment.status = "active"


def _apply_payment_state(db: Session, payment: Payment, rp_payment: Dict[str, Any]) -> bool:
    """Apply a Razorpay payment entity (already authenticated) to our record.

    Returns True when the payment is captured. Raises 409 if the entity does not match
    the stored order. A captured payment is never downgraded.
    """
    if (rp_payment.get("order_id") != payment.razorpay_order_id
            or rp_payment.get("amount") != payment.amount
            or str(rp_payment.get("currency", "")).upper() != payment.currency):
        raise HTTPException(status.HTTP_409_CONFLICT, "Payment does not match the order")

    payment_id = rp_payment.get("id")
    if payment.razorpay_payment_id and payment.razorpay_payment_id != payment_id:
        if payment.status == "captured":
            raise HTTPException(status.HTTP_409_CONFLICT, "Order already paid with a different payment")
    taken = (db.query(Payment).filter(Payment.razorpay_payment_id == payment_id,
                                      Payment.id != payment.id).first())
    if taken is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Payment already used for another order")

    if payment.status == "captured":
        return True

    rp_status = rp_payment.get("status")
    if rp_status == "captured":
        payment.status = "captured"
        payment.razorpay_payment_id = payment_id
        _activate_enrollment(db, payment)
        return True
    if rp_status == "authorized":
        payment.status = "authorized"
        payment.razorpay_payment_id = payment_id
    elif rp_status == "failed":
        payment.status = "failed"
        payment.razorpay_payment_id = payment_id
    return False


@router.post("/create-order", response_model=CreateOrderResponse, summary="Create a Razorpay order for a course")
def create_order(
    payload: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_configured()
    course = (db.query(Course)
              .filter(Course.id == payload.course_id, Course.status == "published").first())
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    if course.is_free or not course.price_amount or course.price_amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This course does not require payment")

    captured = (db.query(Payment).filter(Payment.user_id == current_user.id,
                                         Payment.course_id == course.id,
                                         Payment.status == "captured").first())
    if captured is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already purchased this course")

    # Reuse an open order for the same price instead of creating duplicates
    open_payment = (db.query(Payment)
                    .filter(Payment.user_id == current_user.id, Payment.course_id == course.id,
                            Payment.status.in_(("created", "failed", "authorized")),
                            Payment.amount == course.price_amount,
                            Payment.currency == course.currency)
                    .order_by(Payment.id.desc()).first())
    if open_payment is not None:
        payment = open_payment
    else:
        try:
            order = razorpay_client.create_order(
                amount=course.price_amount,
                currency=course.currency,
                receipt=f"c{course.id}u{current_user.id}-{secrets.token_hex(6)}",
                notes={"course_id": str(course.id), "user_id": str(current_user.id)},
            )
        except RazorpayError as error:
            logger.error(str(error))
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not start payment. Please try again.")
        payment = Payment(user_id=current_user.id, course_id=course.id, amount=course.price_amount,
                          currency=course.currency, razorpay_order_id=order["id"], status="created")
        db.add(payment)
        db.commit()
        db.refresh(payment)

    return CreateOrderResponse(
        payment_id=payment.id, order_id=payment.razorpay_order_id, amount=payment.amount,
        currency=payment.currency, key_id=settings.RAZORPAY_KEY_ID,
    )


@router.post("/verify", response_model=VerifyPaymentResponse, summary="Verify a completed Razorpay payment")
def verify_payment(
    payload: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_configured()
    payment = (db.query(Payment)
               .filter(Payment.razorpay_order_id == payload.razorpay_order_id,
                       Payment.user_id == current_user.id)
               .with_for_update().first())
    if payment is None:  # unknown order, or an order that belongs to someone else
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

    if not razorpay_client.checkout_signature_valid(
            payload.razorpay_order_id, payload.razorpay_payment_id, payload.razorpay_signature):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid payment signature")

    try:
        rp_payment = razorpay_client.fetch_payment(payload.razorpay_payment_id)
    except RazorpayError as error:
        logger.error(str(error))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not confirm payment. Please try again.")
    if rp_payment.get("id") != payload.razorpay_payment_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Payment does not match the order")

    try:
        enrolled = _apply_payment_state(db, payment, rp_payment)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Payment already recorded")
    return VerifyPaymentResponse(status=payment.status, enrolled=enrolled, course_id=payment.course_id)


@router.post("/webhook", summary="Razorpay webhook receiver")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    if not razorpay_client.webhook_signature_valid(raw_body, x_razorpay_signature or ""):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")

    try:
        event = json.loads(raw_body)
        entity_payload = event.get("payload") or {}
        rp_payment = (entity_payload.get("payment") or {}).get("entity") or {}
        rp_order = (entity_payload.get("order") or {}).get("entity") or {}
        event_name = event.get("event", "")
    except (ValueError, AttributeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed webhook payload")

    if event_name not in ("payment.captured", "payment.failed", "payment.authorized", "order.paid"):
        return {"status": "ignored"}

    order_id = rp_payment.get("order_id") or rp_order.get("id")
    payment = (db.query(Payment).filter(Payment.razorpay_order_id == order_id)
               .with_for_update().first()) if order_id else None
    if payment is None:
        return {"status": "ignored"}  # not one of our orders; acknowledge so Razorpay stops retrying

    if event_name in ("payment.captured", "order.paid"):
        # Confirm with Razorpay's API before unlocking, even though the signature is valid
        payment_id = rp_payment.get("id")
        if not payment_id:
            return {"status": "ignored"}
        try:
            rp_payment = razorpay_client.fetch_payment(payment_id)
        except RazorpayError as error:
            logger.error(str(error))
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not confirm payment")

    try:
        _apply_payment_state(db, payment, rp_payment)
        db.commit()
    except HTTPException:
        db.rollback()
        return {"status": "ignored"}  # mismatched payload: acknowledge, never unlock
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
    return {"status": "ok"}
