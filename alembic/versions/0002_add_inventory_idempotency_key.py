"""Add idempotency key to Catalog inventory transactions.

Confirm the actual current Catalog Alembic head before applying this migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_inventory_idempotency"
down_revision = "0001_catalog"  # Confirm with `alembic current` in Product Catalog Service.
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inventory_transactions", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_unique_constraint(
        "uq_inventory_transactions_idempotency_key",
        "inventory_transactions",
        ["idempotency_key"],
    )


def downgrade():
    op.drop_constraint("uq_inventory_transactions_idempotency_key", "inventory_transactions", type_="unique")
    op.drop_column("inventory_transactions", "idempotency_key")
