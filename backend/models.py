"""SQLAlchemy ORM models for the Multi-Store E-commerce ERP."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text,
)
from sqlalchemy.orm import relationship
from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    platform_name = Column(String(32), nullable=False)  # shopee | tiktok
    store_name = Column(String(128), nullable=False)
    api_key = Column(String(255), nullable=True)
    api_secret = Column(String(255), nullable=True)
    access_token = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    orders = relationship("Order", back_populates="store", cascade="all, delete-orphan")
    mappings = relationship("SKUMapping", back_populates="store", cascade="all, delete-orphan")


class MasterSKU(Base):
    __tablename__ = "master_skus"
    id = Column(Integer, primary_key=True, index=True)
    master_sku_code = Column(String(64), unique=True, nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    real_stock = Column(Integer, default=0, nullable=False)
    average_base_cost = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    mappings = relationship("SKUMapping", back_populates="master_sku", cascade="all, delete-orphan")
    inbound_logs = relationship("InboundLog", back_populates="master_sku", cascade="all, delete-orphan")


class SKUMapping(Base):
    __tablename__ = "sku_mappings"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    master_sku_id = Column(Integer, ForeignKey("master_skus.id", ondelete="CASCADE"), nullable=False)
    marketplace_sku_code = Column(String(128), nullable=False, index=True)

    store = relationship("Store", back_populates="mappings")
    master_sku = relationship("MasterSKU", back_populates="mappings")


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    marketplace_order_id = Column(String(128), nullable=False, index=True)
    status = Column(String(32), default="pending", nullable=False)
    total_revenue = Column(Float, default=0.0, nullable=False)
    total_cogs = Column(Float, default=0.0, nullable=False)
    order_date = Column(DateTime(timezone=True), default=_utcnow)
    items_json = Column(Text, nullable=True)  # JSON string of line items

    store = relationship("Store", back_populates="orders")


class InboundLog(Base):
    __tablename__ = "inbound_logs"
    id = Column(Integer, primary_key=True, index=True)
    master_sku_id = Column(Integer, ForeignKey("master_skus.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)
    base_cost = Column(Float, nullable=False)
    shipping_cost = Column(Float, default=0.0, nullable=False)
    final_cogs = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    master_sku = relationship("MasterSKU", back_populates="inbound_logs")
