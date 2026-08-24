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
                "ownerId" UUID NOT NULL REFERENCES "User"(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

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
