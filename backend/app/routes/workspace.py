from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db_connection
from app.utils.datetime import utc_isoformat
from app.services.auth import get_current_user


router = APIRouter(tags=["Pharmacy Workspace"])
limiter = Limiter(key_func=get_remote_address)


class PharmacyProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)
    expiry_alert_days: int = Field(default=90, ge=1, le=365)
    low_stock_alerts: bool = True
    expiry_alerts: bool = True

    @field_validator("name")
    @classmethod
    def name_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Pharmacy name must contain at least 2 characters")
        return value

    @field_validator("phone", "address")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() or None if value is not None else None


def _profile_response(row):
    if not row:
        return {
            "setup_complete": False,
            "profile": {
                "name": "",
                "phone": None,
                "address": None,
                "expiry_alert_days": 90,
                "low_stock_alerts": True,
                "expiry_alerts": True,
            },
        }
    return {
        "setup_complete": True,
        "profile": {
            "name": row["name"],
            "phone": row["phone"],
            "address": row["address"],
            "expiry_alert_days": row["expiry_alert_days"],
            "low_stock_alerts": row["low_stock_alerts"],
            "expiry_alerts": row["expiry_alerts"],
            "onboarding_completed_at": str(row["onboarding_completed_at"]),
            "updated_at": utc_isoformat(row["updated_at"]),
        },
    }


@router.get("/settings/pharmacy")
@limiter.limit("30/minute")
async def get_pharmacy_profile(request: Request, user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT name, phone, address, expiry_alert_days, low_stock_alerts,
                      expiry_alerts, onboarding_completed_at, updated_at
               FROM "PharmacyProfile" WHERE "ownerId" = %s;''',
            (user["user_id"],),
        )
        return _profile_response(cursor.fetchone())
    finally:
        cursor.close()
        conn.close()


@router.put("/settings/pharmacy")
@limiter.limit("15/minute")
async def save_pharmacy_profile(
    request: Request,
    profile: PharmacyProfileUpdate,
    user: dict = Depends(get_current_user),
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''INSERT INTO "PharmacyProfile" (
                   "ownerId", name, phone, address, expiry_alert_days,
                   low_stock_alerts, expiry_alerts
               ) VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT ("ownerId") DO UPDATE SET
                   name = EXCLUDED.name,
                   phone = EXCLUDED.phone,
                   address = EXCLUDED.address,
                   expiry_alert_days = EXCLUDED.expiry_alert_days,
                   low_stock_alerts = EXCLUDED.low_stock_alerts,
                   expiry_alerts = EXCLUDED.expiry_alerts,
                   updated_at = NOW()
               RETURNING name, phone, address, expiry_alert_days, low_stock_alerts,
                         expiry_alerts, onboarding_completed_at, updated_at;''',
            (
                user["user_id"], profile.name, profile.phone, profile.address,
                profile.expiry_alert_days, profile.low_stock_alerts, profile.expiry_alerts,
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return _profile_response(row)
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Pharmacy settings could not be saved") from exc
    finally:
        cursor.close()
        conn.close()


@router.get("/notifications")
@limiter.limit("30/minute")
async def get_notifications(request: Request, user: dict = Depends(get_current_user)):
    owner_id = user["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            '''SELECT expiry_alert_days, low_stock_alerts, expiry_alerts
               FROM "PharmacyProfile" WHERE "ownerId" = %s;''',
            (owner_id,),
        )
        settings = cursor.fetchone() or {
            "expiry_alert_days": 90,
            "low_stock_alerts": True,
            "expiry_alerts": True,
        }
        notifications = []

        if settings["low_stock_alerts"]:
            cursor.execute(
                '''SELECT p.id, p.name, p."minStockLevel",
                          COALESCE(SUM(b.quantity), 0)::int AS stock
                   FROM "Product" p
                   LEFT JOIN "Batch" b ON b."productId" = p.id
                     AND b."ownerId" = p."ownerId" AND b.is_active = TRUE
                   WHERE p."ownerId" = %s AND p.is_active = TRUE
                   GROUP BY p.id, p.name, p."minStockLevel"
                   HAVING COALESCE(SUM(b.quantity), 0) <= p."minStockLevel"
                   ORDER BY stock ASC, p.name ASC
                   LIMIT 25;''',
                (owner_id,),
            )
            for row in cursor.fetchall():
                stock = row["stock"]
                notifications.append({
                    "id": f'low-stock:{row["id"]}',
                    "type": "low_stock",
                    "severity": "critical" if stock == 0 else "warning",
                    "title": "Out of stock" if stock == 0 else "Low stock",
                    "message": f'{row["name"]} has {stock} units remaining (minimum {row["minStockLevel"]}).',
                    "product_id": str(row["id"]),
                    "action_url": "/",
                })

        if settings["expiry_alerts"]:
            cursor.execute(
                '''SELECT b.id, b."productId", b."batchNumber", b.quantity,
                          b."expiryDate", p.name,
                          (b."expiryDate" - CURRENT_DATE)::int AS days_remaining
                   FROM "Batch" b
                   JOIN "Product" p ON p.id = b."productId"
                     AND p."ownerId" = b."ownerId" AND p.is_active = TRUE
                   WHERE b."ownerId" = %s AND b.is_active = TRUE AND b.quantity > 0
                     AND b."expiryDate" <= CURRENT_DATE + %s
                   ORDER BY b."expiryDate" ASC, p.name ASC
                   LIMIT 25;''',
                (owner_id, settings["expiry_alert_days"]),
            )
            for row in cursor.fetchall():
                days = row["days_remaining"]
                if days < 0:
                    title = "Expired stock"
                    timing = f'expired {abs(days)} days ago'
                    severity = "critical"
                elif days == 0:
                    title = "Expires today"
                    timing = "expires today"
                    severity = "critical"
                else:
                    title = "Expiry warning"
                    timing = f'expires in {days} days'
                    severity = "warning" if days <= 30 else "info"
                notifications.append({
                    "id": f'expiry:{row["id"]}',
                    "type": "expiry",
                    "severity": severity,
                    "title": title,
                    "message": f'{row["name"]} batch {row["batchNumber"]} {timing} ({row["quantity"]} units).',
                    "product_id": str(row["productId"]),
                    "batch_id": str(row["id"]),
                    "expiry_date": str(row["expiryDate"]),
                    "action_url": "/",
                })

        severity_order = {"critical": 0, "warning": 1, "info": 2}
        notifications.sort(key=lambda item: (severity_order[item["severity"]], item["title"], item["message"]))
        return {
            "notifications": notifications,
            "total": len(notifications),
            "generated_at": date.today().isoformat(),
            "settings": {
                "expiry_alert_days": settings["expiry_alert_days"],
                "low_stock_alerts": settings["low_stock_alerts"],
                "expiry_alerts": settings["expiry_alerts"],
            },
        }
    finally:
        cursor.close()
        conn.close()
