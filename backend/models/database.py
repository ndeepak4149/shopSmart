from sqlalchemy import (
    Column, String, Float, Integer, Boolean,
    DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from datetime import datetime
import uuid

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class Product(Base):
    """
    A deduplicated product — one row per real-world product.
    e.g. 'Sony WH-1000XM5' is one product even if 50 sellers list it.
    """
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid)
    canonical_name = Column(String, nullable=False)   # our cleaned-up name
    category = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    listings = relationship("Listing", back_populates="product")


class Seller(Base):
    """
    A seller — could be Amazon, a local shop, or any online store.
    We track their history to estimate hidden fees.
    """
    __tablename__ = "sellers"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    domain = Column(String)                           # e.g. 'amazon.com'
    avg_rating = Column(Float)
    review_count = Column(Integer, default=0)
    hidden_fee_rate = Column(Float, default=0.0)      # avg % added at checkout
    avg_shipping_fee = Column(Float, default=0.0)
    seller_type = Column(String)                      # 'online' or 'local'
    created_at = Column(DateTime, default=datetime.utcnow)

    listings = relationship("Listing", back_populates="seller")


class Listing(Base):
    """
    One seller selling one product — the core unit shown to users.
    """
    __tablename__ = "listings"

    id = Column(String, primary_key=True, default=generate_uuid)
    product_id = Column(String, ForeignKey("products.id"))
    seller_id = Column(String, ForeignKey("sellers.id"))
    title = Column(String, nullable=False)            # original title from source
    price = Column(Float, nullable=False)
    url = Column(String)
    image_url = Column(String)
    is_local = Column(Boolean, default=False)         # physical store?
    lat = Column(Float)                               # store location
    lon = Column(Float)
    in_stock = Column(Boolean, default=True)
    source = Column(String)                           # 'channel3', 'ebay', etc.
    similarity_score = Column(Float)                  # from entity resolution
    last_seen = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="listings")
    seller = relationship("Seller", back_populates="listings")
    price_snapshots = relationship("PriceSnapshot", back_populates="listing")


class PriceSnapshot(Base):
    """
    Historical price data — stored every 6 hours by background jobs.
    Powers the price history chart and ML training.
    """
    __tablename__ = "price_snapshots"

    id = Column(String, primary_key=True, default=generate_uuid)
    listing_id = Column(String, ForeignKey("listings.id"))
    price = Column(Float, nullable=False)
    shipping_fee = Column(Float, default=0.0)
    captured_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="price_snapshots")


class PriceAlert(Base):
    """
    User sets an alert: 'tell me when this drops below $X'.
    """
    __tablename__ = "price_alerts"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=False)          # from Supabase Auth
    listing_id = Column(String, ForeignKey("listings.id"))
    target_price = Column(Float)                      # None = any drop
    user_email = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    triggered_at = Column(DateTime)


class UserEvent(Base):
    """
    Every time a user views, clicks, or redirects — we log it.
    This becomes training data for the ranking model over time.
    """
    __tablename__ = "user_events"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String)                          # None if not logged in
    listing_id = Column(String, ForeignKey("listings.id"))
    event_type = Column(String, nullable=False)       # 'view', 'click', 'redirect', 'alert_set'
    session_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
