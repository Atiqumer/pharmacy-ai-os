from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db_connection
from app.services.auth import require_role

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/admin", tags=["Admin - User Management"])


class UpdateUserRole(BaseModel):
    user_id: str
    role: str


class ToggleUserActive(BaseModel):
    user_id: str
    is_active: bool


@router.get("/users")
@limiter.limit("30/minute")
async def list_users(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(require_role("admin")),
):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        offset = (page - 1) * limit
        cursor.execute(
            'SELECT COUNT(*) as total FROM "User";',
        )
        total = cursor.fetchone()["total"]

        cursor.execute(
            """SELECT id, email, full_name, role, is_active, created_at
               FROM "User" ORDER BY created_at DESC LIMIT %s OFFSET %s;""",
            (limit, offset),
        )
        users = cursor.fetchall()

        return {
            "users": [
                {
                    "id": str(u["id"]),
                    "email": u["email"],
                    "full_name": u["full_name"],
                    "role": u["role"],
                    "is_active": u["is_active"],
                    "created_at": str(u["created_at"]),
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "limit": limit,
        }
    finally:
        cursor.close()
        conn.close()


@router.put("/users/role")
@limiter.limit("10/minute")
async def update_user_role(
    request: Request,
    req: UpdateUserRole,
    user: dict = Depends(require_role("admin")),
):
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
    if req.user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE "User" SET role = %s WHERE id = %s RETURNING id, email, full_name, role;',
            (req.role, req.user_id),
        )
        updated = cursor.fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()

        return {
            "message": f"User role updated to {req.role}",
            "user": {
                "id": str(updated["id"]),
                "email": updated["email"],
                "full_name": updated["full_name"],
                "role": updated["role"],
            },
        }
    finally:
        cursor.close()
        conn.close()


@router.put("/users/active")
@limiter.limit("10/minute")
async def toggle_user_active(
    request: Request,
    req: ToggleUserActive,
    user: dict = Depends(require_role("admin")),
):
    if req.user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot change your own account status")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'UPDATE "User" SET is_active = %s WHERE id = %s RETURNING id, email, full_name, is_active;',
            (req.is_active, req.user_id),
        )
        updated = cursor.fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()

        status_text = "activated" if req.is_active else "deactivated"
        return {
            "message": f"User {status_text}",
            "user": {
                "id": str(updated["id"]),
                "email": updated["email"],
                "full_name": updated["full_name"],
                "is_active": updated["is_active"],
            },
        }
    finally:
        cursor.close()
        conn.close()


@router.delete("/users/{target_user_id}")
@limiter.limit("5/minute")
async def delete_user(
    request: Request,
    target_user_id: str,
    user: dict = Depends(require_role("admin")),
):
    if target_user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'DELETE FROM "User" WHERE id = %s RETURNING id, email;',
            (target_user_id,),
        )
        deleted = cursor.fetchone()
        if not deleted:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()

        return {"message": f"User {deleted['email']} deleted"}
    finally:
        cursor.close()
        conn.close()
