"""LMS payment request/response schemas"""
from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    course_id: int = Field(..., ge=1)


class CreateOrderResponse(BaseModel):
    payment_id: int
    order_id: str
    amount: int  # paise
    currency: str
    key_id: str  # public Razorpay key id only


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str = Field(..., min_length=1, max_length=64)
    razorpay_payment_id: str = Field(..., min_length=1, max_length=64)
    razorpay_signature: str = Field(..., min_length=1, max_length=256)


class VerifyPaymentResponse(BaseModel):
    status: str
    enrolled: bool
    course_id: int
