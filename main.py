import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from passlib.context import CryptContext
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User as UserSchema, Product as ProductSchema, Order as OrderSchema, Subscription as SubscriptionSchema, Review as ReviewSchema

# App and CORS
app = FastAPI(title="Digital Trading Store API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth settings
SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Helpers
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    email: Optional[EmailStr] = None

class PublicUser(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    avatar_url: Optional[str] = None

# Utility functions

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_user_by_email(email: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    user = db["user"].find_one({"email": email})
    return user


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = get_user_by_email(token_data.email) if token_data.email else None
    if user is None:
        raise credentials_exception
    return user

# Startup seed data
@app.on_event("startup")
def seed_products_if_empty():
    if db is None:
        return
    count = db["product"].count_documents({})
    if count == 0:
        samples = [
            ProductSchema(
                title="Forex Mastery eBook",
                description="Comprehensive guide to mastering Forex trading.",
                kind="ebook",
                categories=["forex", "education"],
                price=49.0,
                sale_price=29.0,
                is_subscription=False,
                interval=None,
                asset_url="https://example.com/ebooks/forex-mastery.pdf",
                thumbnail_url="https://images.unsplash.com/photo-1553729459-efe14ef6055d",
            ).model_dump(),
            ProductSchema(
                title="Premium Crypto Signals",
                description="High-probability crypto trade signals delivered daily.",
                kind="signal",
                categories=["crypto", "signals"],
                price=0,
                sale_price=None,
                is_subscription=True,
                interval="month",
                asset_url=None,
                thumbnail_url="https://images.unsplash.com/photo-1642790106117-5ac12e8df149",
            ).model_dump(),
            ProductSchema(
                title="Advanced Forex Course",
                description="Video course covering advanced strategies.",
                kind="course",
                categories=["forex", "course"],
                price=199.0,
                sale_price=149.0,
                is_subscription=False,
                interval=None,
                asset_url="https://example.com/courses/advanced-forex",
                thumbnail_url="https://images.unsplash.com/photo-1517245386807-bb43f82c33c4",
            ).model_dump(),
            ProductSchema(
                title="AutoTrader Pro Bot",
                description="Algorithmic trading bot with configurable risk.",
                kind="bot",
                categories=["bot", "automation"],
                price=0,
                sale_price=None,
                is_subscription=True,
                interval="month",
                asset_url=None,
                thumbnail_url="https://images.unsplash.com/photo-1518779578993-ec3579fee39f",
            ).model_dump(),
        ]
        for s in samples:
            create_document("product", s)

# Routes
@app.get("/")
def root():
    return {"message": "Digital Trading Store Backend is running"}

@app.get("/schema")
def get_schema_names():
    return {"schemas": ["user", "product", "order", "subscription", "review"]}

# Auth
class RegisterPayload(BaseModel):
    name: str
    email: EmailStr
    password: str


@app.post("/auth/register", response_model=PublicUser)
def register(payload: RegisterPayload):
    if get_user_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(payload.password)
    user_data = UserSchema(
        name=payload.name,
        email=payload.email,
        hashed_password=hashed_password,
        role="user",
        avatar_url=None,
        is_active=True,
    )
    user_id = create_document("user", user_data)
    created = db["user"].find_one({"_id": ObjectId(user_id)})
    return PublicUser(
        id=str(created["_id"]),
        name=created["name"],
        email=created["email"],
        role=created.get("role", "user"),
        avatar_url=created.get("avatar_url"),
    )


@app.post("/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = create_access_token(data={"sub": user["email"]})
    return Token(access_token=access_token)


@app.get("/auth/me", response_model=PublicUser)
def me(current_user: dict = Depends(get_current_user)):
    return PublicUser(
        id=str(current_user["_id"]),
        name=current_user["name"],
        email=current_user["email"],
        role=current_user.get("role", "user"),
        avatar_url=current_user.get("avatar_url"),
    )

# Products
class ProductCreate(BaseModel):
    title: str
    description: Optional[str] = None
    kind: str
    categories: List[str] = []
    price: float
    sale_price: Optional[float] = None
    is_subscription: bool = False
    interval: Optional[str] = None
    asset_url: Optional[str] = None
    thumbnail_url: Optional[str] = None


@app.post("/products")
def create_product(payload: ProductCreate, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    product_id = create_document("product", ProductSchema(**payload.model_dump()))
    return {"id": product_id}


@app.get("/products")
def list_products():
    products = get_documents("product", {}, limit=100)
    for p in products:
        p["id"] = str(p.pop("_id"))
    return products

# Orders (simplified)
class OrderCreate(BaseModel):
    product_id: str


@app.post("/orders")
def create_order(payload: OrderCreate, current_user: dict = Depends(get_current_user)):
    try:
        prod_obj_id = ObjectId(payload.product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")

    product = db["product"].find_one({"_id": prod_obj_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    amount = float(product.get("sale_price") or product.get("price") or 0)
    order = OrderSchema(
        user_id=str(current_user["_id"]),
        product_id=payload.product_id,
        amount=amount,
        currency="USD",
        status="paid",
        license_key=os.urandom(8).hex() if product.get("kind") in ["course", "bot"] else None,
    )
    order_id = create_document("order", order)
    return {"id": order_id, "status": "paid"}


@app.get("/orders")
def my_orders(current_user: dict = Depends(get_current_user)):
    orders = get_documents("order", {"user_id": str(current_user["_id"])}, limit=100)
    for o in orders:
        o["id"] = str(o.pop("_id"))
    return orders

# Subscriptions
class SubscriptionCreate(BaseModel):
    product_id: str


@app.post("/subscriptions")
def create_subscription(payload: SubscriptionCreate, current_user: dict = Depends(get_current_user)):
    try:
        prod_obj_id = ObjectId(payload.product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")

    product = db["product"].find_one({"_id": prod_obj_id})
    if not product or not product.get("is_subscription"):
        raise HTTPException(status_code=400, detail="Product is not a subscription")

    now = datetime.now(timezone.utc)
    interval = product.get("interval", "month")
    delta = timedelta(days=30 if interval == "month" else 7 if interval == "week" else 365)

    sub = SubscriptionSchema(
        user_id=str(current_user["_id"]),
        product_id=payload.product_id,
        status="active",
        started_at=now,
        current_period_end=now + delta,
    )
    sub_id = create_document("subscription", sub)
    return {"id": sub_id, "status": "active"}


@app.get("/subscriptions")
def my_subscriptions(current_user: dict = Depends(get_current_user)):
    subs = get_documents("subscription", {"user_id": str(current_user["_id"])}, limit=100)
    for s in subs:
        s["id"] = str(s.pop("_id"))
    return subs

# Reviews
class ReviewCreate(BaseModel):
    product_id: str
    rating: int
    comment: Optional[str] = None


@app.post("/reviews")
def add_review(payload: ReviewCreate, current_user: dict = Depends(get_current_user)):
    try:
        prod_obj_id = ObjectId(payload.product_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")

    product = db["product"].find_one({"_id": prod_obj_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    review = ReviewSchema(
        user_id=str(current_user["_id"]),
        product_id=payload.product_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    review_id = create_document("review", review)
    return {"id": review_id}


@app.get("/reviews/{product_id}")
def list_reviews(product_id: str):
    reviews = get_documents("review", {"product_id": product_id}, limit=100)
    for r in reviews:
        r["id"] = str(r.pop("_id"))
    return reviews


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db as _db
        if _db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = _db.name if hasattr(_db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = _db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
