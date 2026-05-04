"""
测试基础设施：内存数据库、测试客户端
"""
import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# 使用文件测试数据库
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """每个测试前重建数据库并初始化赋分规则"""
    Base.metadata.create_all(bind=engine)
    _seed_conversion_rules()
    yield
    Base.metadata.drop_all(bind=engine)


def _seed_conversion_rules():
    """初始化赋分规则"""
    from app.models.score import ConversionRule
    import json
    from app.config import CONVERSION_RULES_PATH

    db = TestingSessionLocal()
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


@pytest.fixture
def db():
    """提供独立的数据库 session"""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """提供测试客户端"""
    return TestClient(app)


@pytest.fixture
def sample_class(db):
    """创建一个测试班级"""
    from app.models.student import ClassGroup
    cls = ClassGroup(name="高三(1)班", grade=12)
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return cls


@pytest.fixture
def sample_student(db, sample_class):
    """创建一个测试学生"""
    from app.models.student import Student
    stu = Student(
        name="张三",
        student_no="2026001",
        class_id=sample_class.id,
        combination="物化生",
    )
    db.add(stu)
    db.commit()
    db.refresh(stu)
    return stu


@pytest.fixture
def sample_exam(db):
    """创建一个测试考试（含9科）"""
    from app.models.exam import Exam, ExamSubject
    exam = Exam(name="第一次模考", exam_date=date(2026, 3, 1), exam_type="模考")
    db.add(exam)
    db.flush()

    subjects = [
        ("语文", 150, False), ("数学", 150, False), ("英语", 150, False),
        ("物理", 100, False), ("历史", 100, False),
        ("化学", 100, True), ("生物", 100, True),
        ("政治", 100, True), ("地理", 100, True),
    ]
    for name, full_score, needs_conv in subjects:
        es = ExamSubject(exam_id=exam.id, subject=name, full_score=full_score, needs_conversion=needs_conv)
        db.add(es)

    db.commit()
    db.refresh(exam)
    return exam
