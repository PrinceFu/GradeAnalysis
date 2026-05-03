import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import BASE_DIR, CONVERSION_RULES_PATH, SECRET_KEY
from app.database import init_db, SessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库和默认数据"""
    init_db()
    _seed_conversion_rules()
    _seed_admin_user()
    yield


app = FastAPI(title="江苏省高考成绩分析系统", lifespan=lifespan)

# Session 中间件
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=86400)

# 静态文件
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# 注册路由
from app.routers import pages, students, exams, scores, analysis, auth  # noqa: E402

app.include_router(auth.router, tags=["认证"])
app.include_router(pages.router)
app.include_router(students.router, prefix="/api/students", tags=["学生管理"])
app.include_router(exams.router, prefix="/api/exams", tags=["考试管理"])
app.include_router(scores.router, prefix="/api/scores", tags=["成绩管理"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["统计分析"])


def _seed_conversion_rules():
    """将 JSON 中的赋分规则写入数据库（如果表为空）"""
    from app.models.score import ConversionRule
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if "conversion_rules" not in inspector.get_table_names():
        return

    db = SessionLocal()
    try:
        if db.query(ConversionRule).count() > 0:
            return
        with open(CONVERSION_RULES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for tier in data["tiers"]:
            rule = ConversionRule(
                tier=tier["tier"],
                percentile_low=tier["percentile_low"],
                percentile_high=tier["percentile_high"],
                converted_low=tier["converted_low"],
                converted_high=tier["converted_high"],
            )
            db.add(rule)
        db.commit()
    finally:
        db.close()


def _seed_admin_user():
    """创建默认管理员账户"""
    from app.models.user import User
    from passlib.context import CryptContext

    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        admin = User(
            username="admin",
            hashed_password=pwd_context.hash("admin123"),
            is_admin=True,
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()
