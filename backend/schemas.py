"""Pydantic v2 schemas."""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str


class StoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    platform_name: str
    store_name: str
    is_active: bool
    sync_enabled: bool = False
    partner_id: Optional[str] = None
    shop_id: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None


class StoreUpdate(BaseModel):
    partner_id: Optional[str] = None
    partner_key: Optional[str] = None
    shop_id: Optional[str] = None
    sync_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class MasterSKUOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    master_sku_code: str
    product_name: str
    real_stock: int
    average_base_cost: float
    reorder_threshold: int = 50


class SKUThresholdUpdate(BaseModel):
    reorder_threshold: int = Field(ge=0)


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    store_id: int
    store_name: Optional[str] = None
    platform_name: Optional[str] = None
    marketplace_order_id: str
    status: str
    total_revenue: float
    total_cogs: float
    order_date: datetime


class OrderTimelineEvent(BaseModel):
    at: datetime
    status: str
    note: Optional[str] = None


class OrderDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    store_id: int
    store_name: Optional[str] = None
    platform_name: Optional[str] = None
    marketplace_order_id: str
    status: str
    total_revenue: float
    total_cogs: float
    order_date: datetime
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    tracking_number: Optional[str] = None
    items: List[dict] = []
    timeline: List[OrderTimelineEvent] = []


class InboundStockRequest(BaseModel):
    master_sku_id: int
    quantity: int = Field(gt=0)
    base_cost: float = Field(ge=0)
    shipping_cost: float = Field(ge=0, default=0.0)


class InboundLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    master_sku_id: int
    quantity: int
    base_cost: float
    shipping_cost: float
    final_cogs: float
    created_at: datetime


class OrderWebhookItem(BaseModel):
    marketplace_sku_code: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)


class OrderWebhookPayload(BaseModel):
    store_id: int
    marketplace_order_id: str
    status: str = "pending"
    items: List[OrderWebhookItem]
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None


class DashboardMetrics(BaseModel):
    total_gmv: float
    total_orders: int
    total_cogs: float
    net_profit: float
    per_store: list


class SettingsOut(BaseModel):
    slack_webhook_url: Optional[str] = None


class SettingsUpdate(BaseModel):
    slack_webhook_url: Optional[str] = None


class LabelBatchRequest(BaseModel):
    order_ids: List[int]
