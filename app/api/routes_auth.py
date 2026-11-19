"""Authentication routes"""
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.auth import authenticate_user, create_access_token, get_current_user, get_password_hash
from app.core.database import get_db
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionType
from app.models.plan import Plan
from app.services.entitlement_service import (
    EntitlementConfigurationError,
    InvalidPlanAssociationError,
    NoValidSubscriptionError,
    resolve_effective_entitlement,
)
from pydantic import BaseModel

router = APIRouter()

class UserCreate(BaseModel):
    email: str
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class SubscriptionResponse(BaseModel):
    id: int
    type: SubscriptionType
    is_active: bool
    start_date: str
    end_date: str | None

class PlanResponse(BaseModel):
    code: str
    name: str
    currency: str | None
    price_amount: int | None
    billing_interval: str | None
    duration_days: int | None
    chat_limit: int | None
    ingestion_limit: int | None

class SubscriptionMetadata(BaseModel):
    id: int
    type: SubscriptionType
    is_active: bool
    start_date: str | None
    end_date: str | None

class EntitlementResponse(BaseModel):
    plan: PlanResponse
    subscription: SubscriptionMetadata | None
    is_free_fallback: bool

@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user account"""
    # Check if user already exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Create default free subscription
    free_plan = db.query(Plan).filter(Plan.code == "FREE").first()
    plan_id = free_plan.id if free_plan else None
    subscription = Subscription(
        user_id=db_user.id,
        plan_id=plan_id,
        type=SubscriptionType.FREE
    )
    db.add(subscription)
    db.commit()

    return db_user

@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return access token"""
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@router.get("/subscriptions", response_model=List[SubscriptionResponse])
def get_user_subscriptions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's subscriptions"""
    subscriptions = db.query(Subscription).filter(Subscription.user_id == current_user.id).all()
    results = []
    for sub in subscriptions:
        results.append(
            SubscriptionResponse(
                id=sub.id,
                type=sub.type,
                is_active=sub.is_active,
                start_date=sub.start_date.isoformat() if sub.start_date else "",
                end_date=sub.end_date.isoformat() if sub.end_date else None,
            )
        )
    return results

@router.get("/entitlements", response_model=EntitlementResponse)
def get_user_entitlements(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's effective entitlement"""
    try:
        plan, subscription, is_free_fallback = resolve_effective_entitlement(db, current_user.id)
        return EntitlementResponse(
            plan=PlanResponse(
                code=plan.code,
                name=plan.name,
                currency=plan.currency,
                price_amount=plan.price_amount,
                billing_interval=plan.billing_interval,
                duration_days=plan.duration_days,
                chat_limit=plan.chat_limit,
                ingestion_limit=plan.ingestion_limit,
            ),
            subscription=SubscriptionMetadata(
                id=subscription.id,
                type=subscription.type,
                is_active=subscription.is_active,
                start_date=subscription.start_date.isoformat() if subscription.start_date else None,
                end_date=subscription.end_date.isoformat() if subscription.end_date else None,
            ) if subscription else None,
            is_free_fallback=is_free_fallback,
        )
    except (EntitlementConfigurationError, InvalidPlanAssociationError) as e:
        raise HTTPException(status_code=500, detail=str(e))

