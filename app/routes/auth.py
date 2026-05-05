from fastapi import APIRouter, Form, Response

from app.config import PASSWORD

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login")
async def login(response: Response, password: str = Form(...)) -> dict:
    if PASSWORD and password == PASSWORD:
        response.set_cookie(
            key="auth_token",
            value=PASSWORD,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30,  # 30 days
            path="/",
        )
        return {"ok": True}
    response.status_code = 401
    return {"ok": False, "error": "密码错误"}
