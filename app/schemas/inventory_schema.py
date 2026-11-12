from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class StockChange(BaseModel):
    quantity: int = Field(gt=0)
    remarks: str | None = Field(default=None, max_length=255)

class InventoryOut(BaseModel):
    product_id: int
    stock_quantity: int

class InventoryTransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    transaction_type: str
    quantity: int
    previous_stock: int
    updated_stock: int
    remarks: str | None
    created_at: datetime

class LowStockProduct(BaseModel):
    product_id: int
    name: str
    sku: str
    stock_quantity: int
    threshold: int
