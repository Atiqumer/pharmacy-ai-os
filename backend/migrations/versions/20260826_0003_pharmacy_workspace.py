"""Add the single-pharmacy workspace profile."""

from alembic import op


revision = "20260826_0003"
down_revision = "20260825_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE "PharmacyProfile" (
            "ownerId" UUID PRIMARY KEY REFERENCES "User"(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(50),
            address VARCHAR(500),
            expiry_alert_days INT NOT NULL DEFAULT 90
                CHECK (expiry_alert_days BETWEEN 1 AND 365),
            low_stock_alerts BOOLEAN NOT NULL DEFAULT TRUE,
            expiry_alerts BOOLEAN NOT NULL DEFAULT TRUE,
            onboarding_completed_at TIMESTAMP NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)


def downgrade():
    op.execute('DROP TABLE IF EXISTS "PharmacyProfile" CASCADE')
