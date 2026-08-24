"""Create the initial production RxOS schema."""

from alembic import op

revision = "20260825_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("""
        CREATE TABLE "User" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL, full_name VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            token_valid_after TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:00',
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE TABLE "Product" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(255) NOT NULL,
            "genericName" VARCHAR(255), category VARCHAR(100),
            "minStockLevel" INT NOT NULL DEFAULT 10 CHECK ("minStockLevel" >= 0),
            "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX product_owner_name_uq ON "Product" ("ownerId", name);
        CREATE TABLE "Supplier" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(255) NOT NULL,
            contact_name VARCHAR(255), phone VARCHAR(50), email VARCHAR(255), address VARCHAR(500),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX supplier_owner_name_uq ON "Supplier" ("ownerId", name);
        CREATE TABLE "Batch" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "batchNumber" VARCHAR(100) NOT NULL,
            "productId" UUID NOT NULL REFERENCES "Product"(id) ON DELETE CASCADE,
            "supplierId" UUID REFERENCES "Supplier"(id) ON DELETE SET NULL,
            quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
            "costPrice" NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK ("costPrice" >= 0),
            "retailPrice" NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK ("retailPrice" >= 0),
            "expiryDate" DATE NOT NULL, "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX batch_owner_product_number_uq ON "Batch" ("ownerId", "productId", "batchNumber");
        CREATE INDEX batch_owner_expiry_idx ON "Batch" ("ownerId", "expiryDate");
        CREATE INDEX batch_owner_product_idx ON "Batch" ("ownerId", "productId");
        CREATE TABLE "StockMovement" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "batchId" UUID NOT NULL REFERENCES "Batch"(id) ON DELETE CASCADE,
            "productId" UUID NOT NULL REFERENCES "Product"(id) ON DELETE CASCADE,
            "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            "createdBy" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
            "quantityChange" INT NOT NULL CHECK ("quantityChange" <> 0),
            "quantityBefore" INT NOT NULL CHECK ("quantityBefore" >= 0),
            "quantityAfter" INT NOT NULL CHECK ("quantityAfter" >= 0),
            reason VARCHAR(30) NOT NULL CHECK (reason IN ('opening','purchase','sale','return','damage','expired','correction','other')),
            note VARCHAR(500), created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE INDEX stock_movement_owner_created_idx ON "StockMovement" ("ownerId", created_at DESC);
        CREATE INDEX stock_movement_batch_idx ON "StockMovement" ("batchId", created_at DESC);
        CREATE TABLE "PurchaseOrder" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "orderNumber" VARCHAR(40) NOT NULL,
            "supplierId" UUID NOT NULL REFERENCES "Supplier"(id) ON DELETE RESTRICT,
            "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            "createdBy" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
            status VARCHAR(30) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','ordered','partially_received','received','cancelled')),
            "expectedDate" DATE, notes VARCHAR(1000), "totalCost" NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK ("totalCost" >= 0),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(), updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX purchase_order_owner_number_uq ON "PurchaseOrder" ("ownerId", "orderNumber");
        CREATE INDEX purchase_order_owner_created_idx ON "PurchaseOrder" ("ownerId", created_at DESC);
        CREATE TABLE "PurchaseOrderItem" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            "purchaseOrderId" UUID NOT NULL REFERENCES "PurchaseOrder"(id) ON DELETE CASCADE,
            "productId" UUID NOT NULL REFERENCES "Product"(id) ON DELETE RESTRICT,
            "orderedQuantity" INT NOT NULL CHECK ("orderedQuantity" > 0),
            "receivedQuantity" INT NOT NULL DEFAULT 0 CHECK ("receivedQuantity" >= 0),
            "costPrice" NUMERIC(12,2) NOT NULL CHECK ("costPrice" >= 0), created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE ("purchaseOrderId", "productId")
        );
        CREATE TABLE "GoodsReceipt" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "purchaseOrderId" UUID NOT NULL REFERENCES "PurchaseOrder"(id) ON DELETE RESTRICT,
            "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            "receivedBy" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
            reference VARCHAR(100), notes VARCHAR(500), received_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE INDEX goods_receipt_order_idx ON "GoodsReceipt" ("purchaseOrderId", received_at DESC);
        CREATE TABLE "GoodsReceiptItem" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "receiptId" UUID NOT NULL REFERENCES "GoodsReceipt"(id) ON DELETE CASCADE,
            "purchaseOrderItemId" UUID NOT NULL REFERENCES "PurchaseOrderItem"(id) ON DELETE RESTRICT,
            "batchId" UUID NOT NULL REFERENCES "Batch"(id) ON DELETE RESTRICT,
            quantity INT NOT NULL CHECK (quantity > 0), created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE TABLE "PasswordReset" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "userId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
            token_hash VARCHAR(64) NOT NULL, expires_at TIMESTAMP NOT NULL, used BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE INDEX password_reset_token_hash_idx ON "PasswordReset" (token_hash);
    """)


def downgrade():
    for table in ["PasswordReset", "GoodsReceiptItem", "GoodsReceipt", "PurchaseOrderItem", "PurchaseOrder", "StockMovement", "Batch", "Supplier", "Product", "User"]:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
