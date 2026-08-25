"""Add pilot product lifecycle and sales operations."""

from alembic import op


revision = "20260825_0002"
down_revision = "20260825_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE "Product"
            ADD COLUMN sku VARCHAR(100),
            ADD COLUMN barcode VARCHAR(100),
            ADD COLUMN manufacturer VARCHAR(255),
            ADD COLUMN strength VARCHAR(100),
            ADD COLUMN dosage_form VARCHAR(100),
            ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
            ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW();
        CREATE UNIQUE INDEX product_owner_sku_uq
            ON "Product" ("ownerId", sku) WHERE sku IS NOT NULL;
        CREATE UNIQUE INDEX product_owner_barcode_uq
            ON "Product" ("ownerId", barcode) WHERE barcode IS NOT NULL;

        ALTER TABLE "Batch"
            ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
            ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW();

        CREATE TABLE "Sale" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            "saleNumber" VARCHAR(40) NOT NULL,
            "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
            "createdBy" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
            status VARCHAR(30) NOT NULL DEFAULT 'completed'
                CHECK (status IN ('completed','partially_returned','refunded')),
            subtotal NUMERIC(14,2) NOT NULL CHECK (subtotal >= 0),
            discount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
            total NUMERIC(14,2) NOT NULL CHECK (total >= 0),
            notes VARCHAR(500),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX sale_owner_number_uq ON "Sale" ("ownerId", "saleNumber");
        CREATE INDEX sale_owner_created_idx ON "Sale" ("ownerId", created_at DESC);

        CREATE TABLE "SaleItem" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            "saleId" UUID NOT NULL REFERENCES "Sale"(id) ON DELETE RESTRICT,
            "productId" UUID NOT NULL REFERENCES "Product"(id) ON DELETE RESTRICT,
            "batchId" UUID NOT NULL REFERENCES "Batch"(id) ON DELETE RESTRICT,
            quantity INT NOT NULL CHECK (quantity > 0),
            "returnedQuantity" INT NOT NULL DEFAULT 0
                CHECK ("returnedQuantity" >= 0 AND "returnedQuantity" <= quantity),
            "unitPrice" NUMERIC(12,2) NOT NULL CHECK ("unitPrice" >= 0),
            "costPrice" NUMERIC(12,2) NOT NULL CHECK ("costPrice" >= 0),
            "lineTotal" NUMERIC(14,2) NOT NULL CHECK ("lineTotal" >= 0),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE INDEX sale_item_sale_idx ON "SaleItem" ("saleId");

        CREATE TABLE "SalesReturn" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            "returnNumber" VARCHAR(40) NOT NULL,
            "saleId" UUID NOT NULL REFERENCES "Sale"(id) ON DELETE RESTRICT,
            "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
            "receivedBy" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
            reason VARCHAR(500) NOT NULL,
            "refundAmount" NUMERIC(14,2) NOT NULL CHECK ("refundAmount" >= 0),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX sales_return_owner_number_uq
            ON "SalesReturn" ("ownerId", "returnNumber");
        CREATE INDEX sales_return_sale_idx ON "SalesReturn" ("saleId", created_at DESC);

        CREATE TABLE "SalesReturnItem" (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            "returnId" UUID NOT NULL REFERENCES "SalesReturn"(id) ON DELETE RESTRICT,
            "saleItemId" UUID NOT NULL REFERENCES "SaleItem"(id) ON DELETE RESTRICT,
            "batchId" UUID NOT NULL REFERENCES "Batch"(id) ON DELETE RESTRICT,
            quantity INT NOT NULL CHECK (quantity > 0),
            "refundAmount" NUMERIC(14,2) NOT NULL CHECK ("refundAmount" >= 0),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
        CREATE INDEX sales_return_item_return_idx ON "SalesReturnItem" ("returnId");
    """)


def downgrade():
    for table in ["SalesReturnItem", "SalesReturn", "SaleItem", "Sale"]:
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
    op.execute("DROP INDEX IF EXISTS product_owner_barcode_uq")
    op.execute("DROP INDEX IF EXISTS product_owner_sku_uq")
    op.execute('ALTER TABLE "Batch" DROP COLUMN IF EXISTS updated_at, DROP COLUMN IF EXISTS is_active')
    op.execute(
        'ALTER TABLE "Product" DROP COLUMN IF EXISTS updated_at, DROP COLUMN IF EXISTS is_active, '
        'DROP COLUMN IF EXISTS dosage_form, DROP COLUMN IF EXISTS strength, '
        'DROP COLUMN IF EXISTS manufacturer, DROP COLUMN IF EXISTS barcode, DROP COLUMN IF EXISTS sku'
    )
