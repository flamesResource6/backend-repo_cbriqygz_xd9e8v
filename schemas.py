"""
Database Schemas for the Digital Trading Store

Collections:
- User: Authentication and profile
- Product: Digital items (ebook, signals, course, bot, etc.)
- Order: Customer purchases
- Subscription: Recurring plans for signals/courses/bots
- Review: Product reviews and ratings
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal
from datetime import datetime

# Users
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    hashed_password: str = Field(..., description="Password hash")
    role: Literal["user", "admin"] = Field("user", description="User role")
    avatar_url: Optional[str] = Field(None, description="Profile image URL")
    is_active: bool = Field(True, description="Is account active")

# Digital products
class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Detailed description")
    
    # type of product: ebook, signal, course, bot
    kind: Literal["ebook", "signal", "course", "bot"] = Field(..., description="Product kind")
    categories: List[str] = Field(default_factory=list, description="Tags/categories")

    price: float = Field(..., ge=0, description="One-time price in USD")
    sale_price: Optional[float] = Field(None, ge=0, description="Discount price in USD")
    
    # For subscriptions (signals/courses/bots)
    is_subscription: bool = Field(False, description="Whether product requires subscription")
    interval: Optional[Literal["week", "month", "year"]] = Field(None, description="Billing interval if subscription")

    # delivery: download url or access details
    asset_url: Optional[str] = Field(None, description="Download or access URL")
    thumbnail_url: Optional[str] = Field(None, description="Preview image")
    rating: float = Field(0, ge=0, le=5, description="Average rating")

# Orders
class Order(BaseModel):
    user_id: str = Field(..., description="User id")
    product_id: str = Field(..., description="Product id")
    amount: float = Field(..., ge=0, description="Charged amount")
    currency: Literal["USD", "EUR", "USDT"] = Field("USD", description="Currency")
    status: Literal["pending", "paid", "failed", "refunded"] = Field("pending", description="Payment status")
    license_key: Optional[str] = Field(None, description="License or access key for bots/courses")

# Subscriptions
class Subscription(BaseModel):
    user_id: str = Field(..., description="User id")
    product_id: str = Field(..., description="Product id (must be subscription)")
    status: Literal["active", "past_due", "canceled"] = Field("active")
    started_at: Optional[datetime] = Field(default=None)
    current_period_end: Optional[datetime] = Field(default=None)

# Reviews
class Review(BaseModel):
    user_id: str
    product_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
