from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.connection import Base

class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inventory_quantity_positive"),
        CheckConstraint("transaction_type IN ('IN', 'OUT')", name="ck_inventory_type_valid"),
        CheckConstraint("previous_stock >= 0 AND updated_stock >= 0", name="ck_inventory_stock_nonnegative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_stock: Mapped[int] = mapped_column(Integer, nullable=False)
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    product: Mapped["Product"] = relationship(back_populates="inventory_transactions")
