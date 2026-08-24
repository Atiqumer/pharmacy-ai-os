import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
logging.getLogger("rxos.access").setLevel(logging.INFO)
logging.getLogger("rxos.error").setLevel(logging.ERROR)
logging.getLogger("rxos.auth").setLevel(logging.INFO)

logger = logging.getLogger("rxos.db")


def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise e


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "User" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "Product" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                "genericName" VARCHAR(255),
                category VARCHAR(100),
                "minStockLevel" INT NOT NULL DEFAULT 10 CHECK ("minStockLevel" >= 0),
                "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "Supplier" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                contact_name VARCHAR(255),
                phone VARCHAR(50),
                email VARCHAR(255),
                address VARCHAR(500),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        cursor.execute('ALTER TABLE "Supplier" ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255);')
        cursor.execute('ALTER TABLE "Supplier" ADD COLUMN IF NOT EXISTS phone VARCHAR(50);')
        cursor.execute('ALTER TABLE "Supplier" ADD COLUMN IF NOT EXISTS email VARCHAR(255);')
        cursor.execute('ALTER TABLE "Supplier" ADD COLUMN IF NOT EXISTS address VARCHAR(500);')
        cursor.execute('ALTER TABLE "Supplier" ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;')

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "Batch" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "batchNumber" VARCHAR(100) NOT NULL,
                "productId" UUID NOT NULL REFERENCES "Product"(id) ON DELETE CASCADE,
                "supplierId" UUID REFERENCES "Supplier"(id) ON DELETE SET NULL,
                quantity INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
                "costPrice" NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK ("costPrice" >= 0),
                "retailPrice" NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK ("retailPrice" >= 0),
                "expiryDate" DATE NOT NULL,
                "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Idempotent schema upgrades for databases created by earlier RxOS
        # versions. These indexes also provide conflict targets for safe CSV
        # upserts and keep each tenant's catalogue independent.
        cursor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS product_owner_name_uq '
            'ON "Product" ("ownerId", name);'
        )
        cursor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS batch_owner_product_number_uq '
            'ON "Batch" ("ownerId", "productId", "batchNumber");'
        )
        cursor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS supplier_owner_name_uq '
            'ON "Supplier" ("ownerId", name);'
        )
        cursor.execute('CREATE INDEX IF NOT EXISTS batch_owner_expiry_idx ON "Batch" ("ownerId", "expiryDate");')
        cursor.execute('CREATE INDEX IF NOT EXISTS batch_owner_product_idx ON "Batch" ("ownerId", "productId");')

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "StockMovement" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "batchId" UUID NOT NULL REFERENCES "Batch"(id) ON DELETE CASCADE,
                "productId" UUID NOT NULL REFERENCES "Product"(id) ON DELETE CASCADE,
                "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                "createdBy" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
                "quantityChange" INT NOT NULL CHECK ("quantityChange" <> 0),
                "quantityBefore" INT NOT NULL CHECK ("quantityBefore" >= 0),
                "quantityAfter" INT NOT NULL CHECK ("quantityAfter" >= 0),
                reason VARCHAR(30) NOT NULL CHECK (
                    reason IN ('opening', 'purchase', 'sale', 'return', 'damage', 'expired', 'correction', 'other')
                ),
                note VARCHAR(500),
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS stock_movement_owner_created_idx '
            'ON "StockMovement" ("ownerId", created_at DESC);'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS stock_movement_batch_idx '
            'ON "StockMovement" ("batchId", created_at DESC);'
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PurchaseOrder" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "orderNumber" VARCHAR(40) NOT NULL,
                "supplierId" UUID NOT NULL REFERENCES "Supplier"(id) ON DELETE RESTRICT,
                "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                "createdBy" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
                status VARCHAR(30) NOT NULL DEFAULT 'draft' CHECK (
                    status IN ('draft', 'ordered', 'partially_received', 'received', 'cancelled')
                ),
                "expectedDate" DATE,
                notes VARCHAR(1000),
                "totalCost" NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK ("totalCost" >= 0),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)
        cursor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS purchase_order_owner_number_uq '
            'ON "PurchaseOrder" ("ownerId", "orderNumber");'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS purchase_order_owner_created_idx '
            'ON "PurchaseOrder" ("ownerId", created_at DESC);'
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PurchaseOrderItem" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "purchaseOrderId" UUID NOT NULL REFERENCES "PurchaseOrder"(id) ON DELETE CASCADE,
                "productId" UUID NOT NULL REFERENCES "Product"(id) ON DELETE RESTRICT,
                "orderedQuantity" INT NOT NULL CHECK ("orderedQuantity" > 0),
                "receivedQuantity" INT NOT NULL DEFAULT 0 CHECK ("receivedQuantity" >= 0),
                "costPrice" NUMERIC(12, 2) NOT NULL CHECK ("costPrice" >= 0),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE ("purchaseOrderId", "productId")
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "GoodsReceipt" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "purchaseOrderId" UUID NOT NULL REFERENCES "PurchaseOrder"(id) ON DELETE RESTRICT,
                "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                "receivedBy" UUID NOT NULL REFERENCES "User"(id) ON DELETE RESTRICT,
                reference VARCHAR(100),
                notes VARCHAR(500),
                received_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS goods_receipt_order_idx '
            'ON "GoodsReceipt" ("purchaseOrderId", received_at DESC);'
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "GoodsReceiptItem" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "receiptId" UUID NOT NULL REFERENCES "GoodsReceipt"(id) ON DELETE CASCADE,
                "purchaseOrderItemId" UUID NOT NULL REFERENCES "PurchaseOrderItem"(id) ON DELETE RESTRICT,
                "batchId" UUID NOT NULL REFERENCES "Batch"(id) ON DELETE RESTRICT,
                quantity INT NOT NULL CHECK (quantity > 0),
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PasswordReset" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                "userId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                token VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        cursor.execute('CREATE INDEX IF NOT EXISTS password_reset_token_idx ON "PasswordReset" (token);')

        conn.commit()
        logger.info("Database tables initialized successfully")
    except Exception as e:
        conn.rollback()
        logger.error(f"Database init failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
