"""LMS course payment records (Razorpay)"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

PAYMENT_STATUSES = ("created", "authorized", "captured", "failed")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payments_user_course", "user_id", "course_id"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # paise
    currency = Column(String(3), nullable=False, default="INR")
    razorpay_order_id = Column(String(64), unique=True, index=True, nullable=False)
    razorpay_payment_id = Column(String(64), unique=True, index=True, nullable=True)
    status = Column(String(20), nullable=False, default="created", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
    course = relationship("Course")
