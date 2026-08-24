from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.database import get_db_connection
from app.services.auth import create_access_token, get_current_user, require_role

router = APIRouter(prefix="/auth", tags=["Authentication"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


@router.post("/signup", response_model=AuthResponse)
async def signup(req: SignupRequest):
    if len(req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            'SELECT id FROM "User" WHERE email = %s LIMIT 1;',
            (req.email,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        cursor.execute(
            """INSERT INTO "User" (id, email, password_hash, full_name, role, created_at)
               VALUES (gen_random_uuid(), %s, crypt(%s, gen_salt('bf')), %s, 'user', NOW())
               RETURNING id, email, full_name, role, created_at;""",
            (req.email, req.password, req.full_name),
        )
        user = cursor.fetchone()
        conn.commit()

        token = create_access_token(str(user["id"]), user["email"], user["role"])

        return AuthResponse(
            token=token,
            user={
                "id": str(user["id"]),
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Signup failed: {str(e)}",
        )
    finally:
        cursor.close()
        conn.close()


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """SELECT id, email, full_name, role, is_active
               FROM "User"
               WHERE email = %s AND password_hash = crypt(%s, password_hash);""",
            (req.email, req.password),
        )
        user = cursor.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact an administrator.",
            )

        token = create_access_token(str(user["id"]), user["email"], user["role"])

        return AuthResponse(
            token=token,
            user={
                "id": str(user["id"]),
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
            },
        )

    finally:
        cursor.close()
        conn.close()


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, email, full_name, role, is_active, created_at FROM "User" WHERE id = %s;',
            (current_user["user_id"],),
        )
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
            "is_active": user["is_active"],
            "created_at": str(user["created_at"]),
        }
    finally:
        cursor.close()
        conn.close()


@router.post("/password-reset-request")
async def password_reset_request(req: PasswordResetRequest):
    import secrets
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM "User" WHERE email = %s;', (req.email,))
        user = cursor.fetchone()

        if not user:
            return {"message": "If the email exists, a reset link has been sent."}

        reset_token = secrets.token_urlsafe(32)
        cursor.execute(
            """INSERT INTO "PasswordReset" (id, "userId", token, expires_at)
               VALUES (gen_random_uuid(), %s, %s, NOW() + INTERVAL '1 hour');""",
            (str(user["id"]), reset_token),
        )
        conn.commit()

        return {
            "message": "If the email exists, a reset link has been sent.",
            "reset_token": reset_token,
        }

    finally:
        cursor.close()
        conn.close()


@router.post("/password-reset-confirm")
async def password_reset_confirm(req: PasswordResetConfirm):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """SELECT "userId" FROM "PasswordReset"
               WHERE token = %s AND used = FALSE AND expires_at > NOW();""",
            (req.token,),
        )
        reset = cursor.fetchone()

        if not reset:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        if len(req.new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

        cursor.execute(
            'UPDATE "User" SET password_hash = crypt(%s, gen_salt(\'bf\')) WHERE id = %s;',
            (req.new_password, str(reset["userId"])),
        )
        cursor.execute(
            'UPDATE "PasswordReset" SET used = TRUE WHERE token = %s;',
            (req.token,),
        )
        conn.commit()

        return {"message": "Password reset successful"}

    finally:
        cursor.close()
        conn.close()
