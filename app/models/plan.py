"""Plan model"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    price_amount = Column(Integer, nullable=True)
    currency = Column(String(3), nullable=False, default="INR")
    billing_interval = Column(String(20), nullable=True)
    duration_days = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    chat_limit = Column(Integer, nullable=True)
    ingestion_limit = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    subscriptions = relationship("Subscription", back_populates="plan")
