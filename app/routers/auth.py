"""认证路由：登录、登出"""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import os

from app.database import get_db
from app.config import BASE_DIR
from app.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """从 session 获取当前用户"""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """要求登录，未登录则重定向"""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(name="auth/login.html", request=request)


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse(
            name="auth/login.html",
            request=request,
            context={"error": "用户名或密码错误"},
        )
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
