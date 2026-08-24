from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db_connection
from app.services.auth import get_current_user

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    contact_name: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=500)


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    contact_name: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None


def _serialize_supplier(row):
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "contact_name": row["contact_name"],
        "phone": row["phone"],
        "email": row["email"],
        "address": row["address"],
        "is_active": row["is_active"],
        "created_at": str(row["created_at"]),
    }


@router.get("")
@limiter.limit("30/minute")
async def list_suppliers(
    request: Request,
    search: str = Query("", max_length=100),
    include_inactive: bool = False,
    user: dict = Depends(get_current_user),
):
    conditions = ['"ownerId" = %s']
    params = [user["user_id"]]
    if not include_inactive:
        conditions.append("is_active = TRUE")
    if search.strip():
        conditions.append("(name ILIKE %s OR contact_name ILIKE %s OR email ILIKE %s)")
        term = f"%{search.strip()}%"
        params.extend([term, term, term])

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""SELECT id, name, contact_name, phone, email, address, is_active, created_at
                FROM "Supplier"
                WHERE {' AND '.join(conditions)}
                ORDER BY is_active DESC, name ASC;""",
            tuple(params),
        )
        return {"suppliers": [_serialize_supplier(row) for row in cursor.fetchall()]}
    finally:
        cursor.close()
        conn.close()


@router.post("", status_code=201)
@limiter.limit("20/minute")
async def create_supplier(
    request: Request,
    supplier: SupplierCreate,
    user: dict = Depends(get_current_user),
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO "Supplier" (
                   id, name, contact_name, phone, email, address, "ownerId"
               ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s)
               ON CONFLICT ("ownerId", name) DO NOTHING
               RETURNING id, name, contact_name, phone, email, address, is_active, created_at;""",
            (
                supplier.name.strip(), supplier.contact_name, supplier.phone,
                str(supplier.email) if supplier.email else None, supplier.address,
                user["user_id"],
            ),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="A supplier with this name already exists")
        conn.commit()
        return _serialize_supplier(row)
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


@router.put("/{supplier_id}")
@limiter.limit("20/minute")
async def update_supplier(
    request: Request,
    supplier_id: UUID,
    updates: SupplierUpdate,
    user: dict = Depends(get_current_user),
):
    values = updates.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="No supplier changes were provided")
    if "email" in values and values["email"] is not None:
        values["email"] = str(values["email"])
    for key in ("name", "contact_name", "phone", "address"):
        if key in values and values[key] is not None:
            values[key] = values[key].strip()

    allowed_columns = {
        "name": "name", "contact_name": "contact_name", "phone": "phone",
        "email": "email", "address": "address", "is_active": "is_active",
    }
    assignments = [f'{allowed_columns[key]} = %s' for key in values]
    params = list(values.values()) + [str(supplier_id), user["user_id"]]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""UPDATE "Supplier" SET {', '.join(assignments)}
                WHERE id = %s AND "ownerId" = %s
                RETURNING id, name, contact_name, phone, email, address, is_active, created_at;""",
            tuple(params),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Supplier not found")
        conn.commit()
        return _serialize_supplier(row)
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
