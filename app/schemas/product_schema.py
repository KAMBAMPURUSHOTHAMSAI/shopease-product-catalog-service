from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator, field_validator

class ProductFields(BaseModel):
    category_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    sku: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    discount_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    stock_quantity: int = Field(default=0, ge=0)
    image_url: str | None = Field(default=None, max_length=500)
    brand: str | None = Field(default=None, max_length=100)
    is_active: bool = True
    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = " ".join(value.split())
        if not value: raise ValueError("Product name must contain meaningful text.")
        return value
    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value): return value.strip().upper()
    @model_validator(mode="after")
    def check_discount(self):
        if self.discount_price is not None and self.discount_price >= self.price:
            raise ValueError("discount_price must be less than price.")
        return self

class ProductCreate(ProductFields):
    pass

class ProductUpdate(ProductFields):
    pass

class ProductPatch(BaseModel):
    category_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    sku: str | None = Field(default=None, min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    discount_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    stock_quantity: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=500)
    brand: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if value is None: return value
        value = " ".join(value.split())
        if not value: raise ValueError("Product name must contain meaningful text.")
        return value
    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value): return value.strip().upper() if value else value

class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_id: int
    name: str
    description: str | None
    sku: str
    price: Decimal
    discount_price: Decimal | None
    stock_quantity: int
    image_url: str | None
    brand: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
    pages: int
