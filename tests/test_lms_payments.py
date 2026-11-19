"""Tests for Razorpay course payments. All Razorpay network calls are mocked."""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.auth import create_access_token, get_password_hash
from app.core.config import settings
from app.main import app
from app.models.course import Course, CourseEnrollment, CourseModule, Lesson
from app.models.payment import Payment
from app.models.user import User
from app.services import razorpay_client

client = TestClient(app)
KEY_SECRET = "test_key_secret_not_real"
WEBHOOK_SECRET = "test_webhook_secret_not_real"
PRICE = 99900


def sign(order_id, payment_id, secret=KEY_SECRET):
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


class FakeRazorpay:
    """Stands in for Razorpay's API; records calls and serves canned payment entities."""

    def __init__(self):
        self.orders = []
        self.payments = {}
        self.fetches = 0

    def create_order(self, amount, currency, receipt, notes):
        self.orders.append({"amount": amount, "currency": currency, "notes": notes})
        return {"id": f"order_test{len(self.orders):03d}", "amount": amount, "currency": currency}

    def fetch_payment(self, payment_id):
        self.fetches += 1
        return self.payments[payment_id]

    def set_payment(self, payment_id, order_id, status, amount=PRICE, currency="INR"):
        self.payments[payment_id] = {"id": payment_id, "order_id": order_id, "status": status,
                                     "amount": amount, "currency": currency}


@pytest.fixture
def rzp(monkeypatch):
    fake = FakeRazorpay()
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_publicid")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", SecretStr(KEY_SECRET))
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", SecretStr(WEBHOOK_SECRET))
    monkeypatch.setattr(razorpay_client, "create_order", fake.create_order)
    monkeypatch.setattr(razorpay_client, "fetch_payment", fake.fetch_payment)
    return fake


@pytest.fixture
def env(TestingSessionLocal):
    db = TestingSessionLocal()
    course = Course(slug="pay-test-course", title="Paid", status="published", is_free=False,
                    price_amount=PRICE, currency="INR")
    other = Course(slug="pay-test-other", title="Other", status="published", is_free=False,
                   price_amount=5000, currency="INR")
    db.add_all([course, other])
    db.flush()
    module = CourseModule(course_id=course.id, title="M", display_order=1)
    db.add(module)
    db.flush()
    preview = Lesson(module_id=module.id, title="Preview", display_order=1, is_preview=True,
                     media_url="https://www.youtube.com/watch?v=aaaaaaaaaaa")
    paid = Lesson(module_id=module.id, title="Paid", display_order=2, is_preview=False,
                  media_url="https://www.youtube.com/watch?v=bbbbbbbbbbb")
    users = []
    for name in ("buyer", "intruder"):
        user = User(username=f"pay_{name}", email=f"pay_{name}@example.com",
                    hashed_password=get_password_hash("Secret123!"), is_active=True)
        db.add(user)
        users.append(user)
    db.add_all([preview, paid])
    db.commit()
    for obj in (course, other, preview, paid, *users):
        db.refresh(obj)

    def headers(user):
        return {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}

    ctx = type("Ctx", (), {})()
    ctx.db, ctx.course, ctx.other, ctx.preview, ctx.paid = db, course, other, preview, paid
    ctx.buyer, ctx.intruder = users
    ctx.buyer_h, ctx.intruder_h = headers(users[0]), headers(users[1])
    yield ctx
    db.rollback()
    db.query(Payment).delete()
    db.query(CourseEnrollment).delete()
    for c in (course, other):
        db.delete(db.get(Course, c.id))
    for u in users:
        db.delete(db.get(User, u.id))
    db.commit()
    db.close()


def _order(env, headers=None, course_id=None):
    res = client.post("/api/lms/payments/create-order",
                      json={"course_id": course_id or env.course.id}, headers=headers or env.buyer_h)
    assert res.status_code == 200, res.text
    return res.json()


def _verify(order_id, payment_id, signature=None, headers=None, env=None):
    return client.post("/api/lms/payments/verify", headers=headers or env.buyer_h, json={
        "razorpay_order_id": order_id, "razorpay_payment_id": payment_id,
        "razorpay_signature": signature or sign(order_id, payment_id)})


def _lesson_status(env, lesson, headers=None):
    return client.get(f"/api/lms/learner/lessons/{lesson.id}", headers=headers or env.buyer_h).status_code


def _webhook(event, payment_id, order_id, status, secret=WEBHOOK_SECRET, signature=None):
    body = json.dumps({"event": event, "payload": {"payment": {"entity": {
        "id": payment_id, "order_id": order_id, "status": status,
        "amount": PRICE, "currency": "INR"}}}}).encode()
    sig = signature or hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/api/lms/payments/webhook", content=body,
                       headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})


# --- create-order ---------------------------------------------------------

def test_create_order_uses_database_price_and_hides_secrets(env, rzp):
    res = client.post("/api/lms/payments/create-order",
                      json={"course_id": env.course.id, "amount": 1, "user_id": env.intruder.id},
                      headers=env.buyer_h)
    body = res.json()
    assert res.status_code == 200
    assert (body["amount"], body["currency"], body["key_id"]) == (PRICE, "INR", "rzp_test_publicid")
    assert rzp.orders == [{"amount": PRICE, "currency": "INR",
                           "notes": {"course_id": str(env.course.id), "user_id": str(env.buyer.id)}}]
    payment = env.db.query(Payment).filter_by(razorpay_order_id=body["order_id"]).one()
    assert (payment.user_id, payment.amount, payment.status) == (env.buyer.id, PRICE, "created")
    assert KEY_SECRET not in res.text and WEBHOOK_SECRET not in res.text


def test_create_order_reuses_open_order(env, rzp):
    first, second = _order(env), _order(env)
    assert first["order_id"] == second["order_id"] and len(rzp.orders) == 1


def test_create_order_requires_auth(env, rzp):
    assert client.post("/api/lms/payments/create-order", json={"course_id": env.course.id}).status_code == 401
    assert rzp.orders == []


def test_create_order_invalid_course(env, rzp):
    res = client.post("/api/lms/payments/create-order", json={"course_id": 999999}, headers=env.buyer_h)
    assert res.status_code == 404 and rzp.orders == []


def test_create_order_unconfigured_returns_503(env, monkeypatch):
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", None)
    res = client.post("/api/lms/payments/create-order", json={"course_id": env.course.id}, headers=env.buyer_h)
    assert res.status_code == 503


# --- verify ---------------------------------------------------------------

def test_invalid_signature_rejected(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "captured")
    res = _verify(order["order_id"], "pay_1", signature="0" * 64, env=env)
    assert res.status_code == 400
    assert _lesson_status(env, env.paid) == 403
    assert env.db.query(CourseEnrollment).count() == 0


def test_signature_made_with_wrong_secret_rejected(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "captured")
    res = _verify(order["order_id"], "pay_1", signature=sign(order["order_id"], "pay_1", "other"), env=env)
    assert res.status_code == 400


def test_other_users_order_rejected(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "captured")
    res = _verify(order["order_id"], "pay_1", headers=env.intruder_h, env=env)
    assert res.status_code == 404
    assert env.db.query(CourseEnrollment).count() == 0


def test_payment_for_different_order_or_amount_rejected(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_other_order", "order_someone_else", "captured")
    assert _verify(order["order_id"], "pay_other_order", env=env).status_code == 409
    rzp.set_payment("pay_cheap", order["order_id"], "captured", amount=100)
    assert _verify(order["order_id"], "pay_cheap", env=env).status_code == 409
    assert env.db.query(CourseEnrollment).count() == 0


def test_authorized_payment_does_not_unlock(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "authorized")
    res = _verify(order["order_id"], "pay_1", env=env)
    assert res.status_code == 200 and res.json() == {"status": "authorized", "enrolled": False,
                                                       "course_id": env.course.id}
    assert _lesson_status(env, env.paid) == 403
    assert env.db.query(CourseEnrollment).count() == 0


def test_failed_payment_does_not_unlock_and_retry_can_succeed(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "failed")
    res = _verify(order["order_id"], "pay_1", env=env)
    assert res.json()["enrolled"] is False and _lesson_status(env, env.paid) == 403
    rzp.set_payment("pay_2", order["order_id"], "captured")
    assert _verify(order["order_id"], "pay_2", env=env).json()["enrolled"] is True
    assert _lesson_status(env, env.paid) == 200


def test_captured_payment_enrolls_and_unlocks(env, rzp):
    assert _lesson_status(env, env.preview) == 200
    assert _lesson_status(env, env.paid) == 403
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "captured")
    res = _verify(order["order_id"], "pay_1", env=env)
    assert res.status_code == 200 and res.json()["enrolled"] is True
    assert _lesson_status(env, env.paid) == 200
    assert _lesson_status(env, env.paid, headers=env.intruder_h) == 403  # other users stay locked
    assert client.get(f"/api/lms/learner/lessons/{env.paid.id}").status_code == 401  # anonymous too
    assert (env.db.query(Payment).one().status, env.db.query(CourseEnrollment).count()) == ("captured", 1)


def test_duplicate_verification_is_idempotent(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "captured")
    for _ in range(3):
        assert _verify(order["order_id"], "pay_1", env=env).json()["enrolled"] is True
    assert env.db.query(CourseEnrollment).count() == 1
    assert client.post("/api/lms/payments/create-order", json={"course_id": env.course.id},
                       headers=env.buyer_h).status_code == 409  # cannot buy twice


def test_enrollment_without_captured_payment_does_not_unlock_paid_course(env, rzp):
    env.db.add(CourseEnrollment(user_id=env.buyer.id, course_id=env.course.id, status="active"))
    env.db.commit()
    assert _lesson_status(env, env.paid) == 403
    assert _lesson_status(env, env.preview) == 200


def test_unrelated_enrollments_untouched(env, rzp):
    env.db.add(CourseEnrollment(user_id=env.intruder.id, course_id=env.other.id, status="active"))
    env.db.commit()
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "captured")
    _verify(order["order_id"], "pay_1", env=env)
    rows = {(e.user_id, e.course_id) for e in env.db.query(CourseEnrollment).all()}
    assert rows == {(env.intruder.id, env.other.id), (env.buyer.id, env.course.id)}


def test_public_responses_never_expose_youtube_urls(env, rzp):
    order = _order(env)
    assert "youtube" not in client.get("/api/lms/catalog/courses").text.lower()
    assert "youtube" not in client.get(f"/api/lms/catalog/courses/{env.course.slug}").text.lower()
    assert "youtube" not in json.dumps(order).lower()


# --- webhook --------------------------------------------------------------

def test_webhook_invalid_signature_rejected(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "captured")
    res = _webhook("payment.captured", "pay_1", order["order_id"], "captured", signature="bad")
    assert res.status_code == 400
    res = _webhook("payment.captured", "pay_1", order["order_id"], "captured", secret="wrong")
    assert res.status_code == 400
    assert env.db.query(CourseEnrollment).count() == 0 and rzp.fetches == 0


def test_webhook_captured_enrolls_once_even_when_duplicated(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "captured")
    for _ in range(3):
        assert _webhook("payment.captured", "pay_1", order["order_id"], "captured").status_code == 200
    assert _webhook("order.paid", "pay_1", order["order_id"], "captured").status_code == 200
    assert env.db.query(CourseEnrollment).count() == 1
    assert _lesson_status(env, env.paid) == 200


def test_webhook_does_not_trust_payload_status(env, rzp):
    """A signed webhook claiming capture is still checked against Razorpay's API."""
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "authorized")
    assert _webhook("payment.captured", "pay_1", order["order_id"], "captured").status_code == 200
    assert env.db.query(CourseEnrollment).count() == 0
    assert _lesson_status(env, env.paid) == 403


def test_webhook_failed_and_authorized_do_not_unlock(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "failed")
    assert _webhook("payment.failed", "pay_1", order["order_id"], "failed").status_code == 200
    assert env.db.query(Payment).one().status == "failed"
    rzp.set_payment("pay_2", order["order_id"], "authorized")
    assert _webhook("payment.authorized", "pay_2", order["order_id"], "authorized").status_code == 200
    assert env.db.query(CourseEnrollment).count() == 0 and _lesson_status(env, env.paid) == 403


def test_webhook_failure_never_downgrades_captured(env, rzp):
    order = _order(env)
    rzp.set_payment("pay_1", order["order_id"], "captured")
    _verify(order["order_id"], "pay_1", env=env)
    rzp.set_payment("pay_x", order["order_id"], "failed")
    _webhook("payment.failed", "pay_x", order["order_id"], "failed")
    env.db.expire_all()
    assert env.db.query(Payment).one().status == "captured"
    assert _lesson_status(env, env.paid) == 200


def test_webhook_unknown_order_is_acknowledged(env, rzp):
    res = _webhook("payment.captured", "pay_z", "order_unknown", "captured")
    assert res.status_code == 200 and res.json()["status"] == "ignored"
