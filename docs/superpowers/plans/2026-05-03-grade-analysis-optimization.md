# 成绩分析系统全面优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 对江苏高考成绩分析系统进行全面优化，分三阶段：基础加固、安全+性能、UI升级

**Architecture:** 保持现有 FastAPI + SQLAlchemy + Jinja2 + Bootstrap 5 + ECharts 架构，修复代码缺陷，添加认证，优化查询性能，升级前端为现代仪表盘风格

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0, SQLite, Jinja2, Bootstrap 5, ECharts 5, pytest, passlib[bcrypt]

---

## 阶段 1：基础加固

### Task 1: 项目配置 — .gitignore 和环境变量

**Files:**
- Create: `.gitignore`
- Modify: `app/config.py`
- Modify: `requirements.txt`

- [ ] **Step 1: 创建 .gitignore**

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.eggs/
*.egg

# Virtual Environment
.venv/
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Database
*.db

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/
```

- [ ] **Step 2: 修改 config.py — 密钥从环境变量读取**

```python
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'scores.db')}"
CONVERSION_RULES_PATH = os.path.join(BASE_DIR, "data", "conversion_rules.json")

SECRET_KEY = os.environ.get("GRADE_SECRET_KEY", "jiangsu-gaokao-grade-analysis-2026")
```

- [ ] **Step 3: 修改 requirements.txt — 移除冗余 openpyxl**

```txt
fastapi==0.115.0
uvicorn==0.30.6
sqlalchemy==2.0.35
jinja2==3.1.4
pandas==2.2.3
python-multipart==0.0.12
aiofiles==24.1.0
passlib[bcrypt]==1.7.4
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore app/config.py requirements.txt
git commit -m "chore: add .gitignore, env-based secret key, clean dependencies"
```

### Task 2: 修复 conversion_service.py — 删除 stub 函数，保留 v2

**Files:**
- Modify: `app/services/conversion_service.py`
- Modify: `app/services/score_service.py`

- [ ] **Step 1: 重写 conversion_service.py — 删除 v1 和 _get_tier，重命名 v2**

```python
"""
江苏省高考等级赋分核心算法

5等21级，仅对化学、生物、政治、地理四门赋分科目执行。
两遍算法：
  1. 按原始分排名，百分位分档
  2. 档内线性插值得出赋分
"""

from sqlalchemy.orm import Session

from app.models.score import Score, ConversionRule
from app.models.exam import ExamSubject

# 需要赋分的科目
CONVERSION_SUBJECTS = {"化学", "生物", "思想政治", "地理"}


def convert_scores_for_subject(db: Session, exam_subject_id: int) -> list[dict]:
    """
    对某次考试的某个赋分科目执行等级赋分，返回 [{student_id, converted_score}, ...]
    一次遍历完成分档+插值
    """
    rules = db.query(ConversionRule).order_by(ConversionRule.percentile_low).all()
    if not rules:
        raise ValueError("赋分规则表为空，请先初始化 conversion_rules")

    scores = (
        db.query(Score)
        .filter(Score.exam_subject_id == exam_subject_id)
        .order_by(Score.raw_score.desc())
        .all()
    )
    if not scores:
        return []

    total = len(scores)

    # 第一遍：计算每个人的百分位和等级
    tier_map: dict[str, list[int]] = {}  # tier -> [index_in_scores]
    for rank_idx, score in enumerate(scores):
        percentile = (rank_idx / total) * 100
        matched_tier = _find_tier(percentile, rules)
        score._tier = matched_tier.tier
        score._percentile = percentile
        tier_map.setdefault(matched_tier.tier, []).append(rank_idx)

    # 第二遍：对每个等级内的学生做线性插值
    results = []
    for tier_name, indices in tier_map.items():
        rule = next(r for r in rules if r.tier == tier_name)
        tier_students = [scores[i] for i in indices]
        y_high = max(s.raw_score for s in tier_students)
        y_low = min(s.raw_score for s in tier_students)
        t_low = rule.converted_low
        t_high = rule.converted_high

        for s in tier_students:
            if y_high == y_low:
                converted = (t_low + t_high) / 2
            else:
                converted = t_low + (s.raw_score - y_low) * (t_high - t_low) / (y_high - y_low)
            converted = round(converted)
            converted = max(40, min(100, converted))
            s.converted_score = float(converted)
            results.append({"student_id": s.student_id, "converted_score": s.converted_score})

    db.flush()
    return results


def convert_all_subjects(db: Session, exam_id: int) -> dict[str, list[dict]]:
    """
    对某次考试的所有赋分科目执行等级赋分
    返回 {subject_name: [{student_id, converted_score}, ...]}
    """
    exam_subjects = (
        db.query(ExamSubject)
        .filter(ExamSubject.exam_id == exam_id, ExamSubject.needs_conversion == True)
        .all()
    )

    all_results = {}
    for es in exam_subjects:
        results = convert_scores_for_subject(db, es.id)
        all_results[es.subject] = results

    return all_results


def _find_tier(percentile: float, rules: list[ConversionRule]) -> ConversionRule:
    """根据百分位找到对应的赋分等级"""
    for rule in rules:
        if rule.percentile_low <= percentile < rule.percentile_high:
            return rule
    return rules[-1]
```

- [ ] **Step 2: 更新 score_service.py 中的 import**

将 `from app.services.conversion_service import CONVERSION_SUBJECTS, convert_scores_for_subject_v2` 改为 `from app.services.conversion_service import CONVERSION_SUBJECTS, convert_scores_for_subject`

将 `return convert_scores_for_subject_v2(db, exam_subject_id)` 改为 `return convert_scores_for_subject(db, exam_subject_id)`

- [ ] **Step 3: Commit**

```bash
git add app/services/conversion_service.py app/services/score_service.py
git commit -m "fix: remove broken v1 conversion function, keep only working v2 implementation"
```

### Task 3: 修复 deprecated SQLAlchemy API

**Files:**
- Modify: `app/routers/students.py:67,95`
- Modify: `app/routers/exams.py:48,91`
- Modify: `app/routers/scores.py:64`
- Modify: `app/services/score_service.py:69`
- Modify: `app/services/stats_service.py:20,53,146`

- [ ] **Step 1: 全局替换 db.query(Model).get(id) 为 db.get(Model, id)**

在每个文件中搜索 `.get(` 并替换：

**students.py:67**
```python
# 原: s = db.query(Student).get(student_id)
s = db.get(Student, student_id)
```

**students.py:95**
```python
# 原: stu = db.query(Student).get(student_id)
stu = db.get(Student, student_id)
```

**exams.py:48**
```python
# 原: exam = db.query(Exam).get(exam_id)
exam = db.get(Exam, exam_id)
```

**exams.py:91**
```python
# 原: exam = db.query(Exam).get(exam_id)
exam = db.get(Exam, exam_id)
```

**scores.py:64**
```python
# 原: es = db.query(ExamSubject).get(exam_subject_id)
es = db.get(ExamSubject, exam_subject_id)
```

**score_service.py:69**
```python
# 原: student = db.query(Student).get(student_id)
student = db.get(Student, student_id)
```

**stats_service.py:20**
```python
# 原: exam_subject = db.query(ExamSubject).get(exam_subject_id)
exam_subject = db.get(ExamSubject, exam_subject_id)
```

**stats_service.py:53**
```python
# 原: exam_subject = db.query(ExamSubject).get(exam_subject_id)
exam_subject = db.get(ExamSubject, exam_subject_id)
```

**stats_service.py:146**
```python
# 原: student = db.query(Student).get(student_id)
student = db.get(Student, student_id)
```

- [ ] **Step 2: Commit**

```bash
git add app/routers/ app/services/
git commit -m "fix: replace deprecated db.query().get() with db.get() for SQLAlchemy 2.0"
```

### Task 4: 迁移 main.py 到 lifespan 上下文管理器

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: 重写 main.py**

```python
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, CONVERSION_RULES_PATH
from app.database import init_db, SessionLocal, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库和默认数据"""
    init_db()
    _seed_conversion_rules()
    yield


app = FastAPI(title="江苏省高考成绩分析系统", lifespan=lifespan)

# 静态文件
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# 注册路由
from app.routers import pages, students, exams, scores, analysis  # noqa: E402

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
```

- [ ] **Step 2: Commit**

```bash
git add app/main.py
git commit -m "refactor: migrate from deprecated on_event to lifespan context manager"
```

### Task 5: 测试基础设施 — pytest fixtures

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: 创建 tests/conftest.py**

```python
"""
测试基础设施：内存数据库、测试客户端
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# 使用内存数据库进行测试
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
    """每个测试前重建数据库"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
        preferred_subject="物理",
        elective_1="化学",
        elective_2="生物",
    )
    db.add(stu)
    db.commit()
    db.refresh(stu)
    return stu


@pytest.fixture
def sample_exam(db):
    """创建一个测试考试（含9科）"""
    from app.models.exam import Exam, ExamSubject
    exam = Exam(name="第一次模考", exam_date="2026-03-01", exam_type="模考")
    db.add(exam)
    db.flush()

    subjects = [
        ("语文", 150, False), ("数学", 150, False), ("英语", 150, False),
        ("物理", 100, False), ("历史", 100, False),
        ("化学", 100, True), ("生物", 100, True),
        ("思想政治", 100, True), ("地理", 100, True),
    ]
    for name, full_score, needs_conv in subjects:
        es = ExamSubject(exam_id=exam.id, subject=name, full_score=full_score, needs_conversion=needs_conv)
        db.add(es)

    db.commit()
    db.refresh(exam)
    return exam
```

- [ ] **Step 2: 创建 tests/__init__.py（空文件）**

- [ ] **Step 3: Commit**

```bash
git add tests/
git commit -m "test: add pytest infrastructure with fixtures for db, client, sample data"
```

### Task 6: 学生管理 API 测试

**Files:**
- Create: `tests/test_students.py`

- [ ] **Step 1: 创建测试文件**

```python
"""学生管理 API 测试"""


def test_create_class(client):
    resp = client.post("/api/students/classes", json={"name": "高三(1)班", "grade": 12})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "高三(1)班"
    assert data["grade"] == 12
    assert "id" in data


def test_list_classes(client, sample_class):
    resp = client.get("/api/students/classes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "高三(1)班"


def test_create_student(client, sample_class):
    resp = client.post("/api/students/", json={
        "name": "李四",
        "student_no": "2026002",
        "class_id": sample_class.id,
        "preferred_subject": "历史",
        "elective_1": "政治",
        "elective_2": "地理",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "李四"
    assert data["student_no"] == "2026002"


def test_create_student_duplicate_no(client, sample_class, sample_student):
    resp = client.post("/api/students/", json={
        "name": "王五",
        "student_no": "2026001",  # 与 sample_student 相同
        "class_id": sample_class.id,
        "preferred_subject": "物理",
        "elective_1": "化学",
        "elective_2": "生物",
    })
    assert resp.status_code == 400
    assert "学号已存在" in resp.json()["detail"]


def test_list_students(client, sample_student):
    resp = client.get("/api/students/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "张三"


def test_list_students_by_class(client, sample_student, sample_class):
    resp = client.get(f"/api/students/?class_id={sample_class.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["class_id"] == sample_class.id


def test_get_student(client, sample_student):
    resp = client.get(f"/api/students/{sample_student.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "张三"
    assert data["student_no"] == "2026001"


def test_get_student_not_found(client):
    resp = client.get("/api/students/9999")
    assert resp.status_code == 404


def test_delete_student(client, sample_student):
    resp = client.delete(f"/api/students/{sample_student.id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # 确认已删除
    resp = client.get(f"/api/students/{sample_student.id}")
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试验证**

```bash
cd "/Users/tigerwang/Documents/vibe coding project/成绩分析系统"
python -m pytest tests/test_students.py -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_students.py
git commit -m "test: add student CRUD API tests"
```

### Task 7: 考试管理 API 测试

**Files:**
- Create: `tests/test_exams.py`

- [ ] **Step 1: 创建测试文件**

```python
"""考试管理 API 测试"""
from app.models.exam import ExamSubject
from app.database import SessionLocal


def test_create_exam(client):
    resp = client.post("/api/exams/", json={
        "name": "第二次模考",
        "exam_date": "2026-04-01",
        "exam_type": "模考",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "第二次模考"
    assert "id" in data


def test_create_exam_auto_creates_subjects(client):
    """创建考试后应自动生成9个科目"""
    resp = client.post("/api/exams/", json={
        "name": "测试考试",
        "exam_date": "2026-04-01",
        "exam_type": "模考",
    })
    exam_id = resp.json()["id"]

    # 获取考试详情，验证科目数
    resp = client.get(f"/api/exams/{exam_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["subjects"]) == 9

    # 验证包含赋分科目
    subjects = [s["subject"] for s in data["subjects"]]
    assert "化学" in subjects
    assert "生物" in subjects
    assert "思想政治" in subjects
    assert "地理" in subjects


def test_list_exams(client, sample_exam):
    resp = client.get("/api/exams/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "第一次模考"


def test_get_exam(client, sample_exam):
    resp = client.get(f"/api/exams/{sample_exam.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "第一次模考"
    assert len(data["subjects"]) == 9


def test_get_exam_not_found(client):
    resp = client.get("/api/exams/9999")
    assert resp.status_code == 404


def test_delete_exam_cascades(client, sample_exam):
    """删除考试应级联删除科目"""
    exam_id = sample_exam.id
    resp = client.delete(f"/api/exams/{exam_id}")
    assert resp.status_code == 200

    # 考试已删除
    resp = client.get(f"/api/exams/{exam_id}")
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行测试验证**

```bash
python -m pytest tests/test_exams.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_exams.py
git commit -m "test: add exam CRUD API tests"
```

### Task 8: 成绩录入与转换 API 测试

**Files:**
- Create: `tests/test_scores.py`

- [ ] **Step 1: 创建测试文件**

```python
"""成绩录入与赋分转换 API 测试"""


def test_enter_single_score(client, sample_student, sample_exam):
    """录入单条成绩"""
    # 获取语文科目的 exam_subject_id
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    yuwen = next(s for s in subjects if s["subject"] == "语文")

    resp = client.post("/api/scores/entry", json={
        "student_id": sample_student.id,
        "exam_subject_id": yuwen["id"],
        "raw_score": 120.0,
    })
    assert resp.status_code == 200
    assert resp.json()["raw_score"] == 120.0


def test_batch_scores(client, sample_student, sample_exam):
    """批量录入成绩"""
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    shuxue = next(s for s in subjects if s["subject"] == "数学")

    resp = client.post("/api/scores/batch", json={
        "exam_subject_id": shuxue["id"],
        "scores": [
            {"student_id": sample_student.id, "raw_score": 135.0},
        ],
    })
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_score_conversion(client, sample_student, sample_exam):
    """赋分科目转换"""
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    huaxue = next(s for s in subjects if s["subject"] == "化学")

    # 先录入成绩
    client.post("/api/scores/entry", json={
        "student_id": sample_student.id,
        "exam_subject_id": huaxue["id"],
        "raw_score": 85.0,
    })

    # 触发赋分
    resp = client.post(f"/api/scores/convert/{huaxue['id']}")
    assert resp.status_code == 200
    assert resp.json()["converted_count"] == 1


def test_total_score(client, sample_student, sample_exam):
    """总分计算（3+1+2）"""
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()

    # 录入所有科目的成绩
    scores_map = {
        "语文": 120, "数学": 135, "英语": 110,
        "物理": 85, "化学": 80, "生物": 78,
    }
    for subj_name, score in scores_map.items():
        es = next(s for s in subjects if s["subject"] == subj_name)
        client.post("/api/scores/entry", json={
            "student_id": sample_student.id,
            "exam_subject_id": es["id"],
            "raw_score": float(score),
        })

    # 触发赋分科目转换
    for subj_name in ["化学", "生物"]:
        es = next(s for s in subjects if s["subject"] == subj_name)
        client.post(f"/api/scores/convert/{es['id']}")

    # 获取总分
    resp = client.get(f"/api/scores/totals/{sample_exam.id}/{sample_student.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert data["total"] > 0
    assert "scores" in data
```

- [ ] **Step 2: 运行测试验证**

```bash
python -m pytest tests/test_scores.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_scores.py
git commit -m "test: add score entry and conversion API tests"
```

### Task 9: 统计分析 API 测试

**Files:**
- Create: `tests/test_analysis.py`

- [ ] **Step 1: 创建测试文件**

```python
"""统计分析 API 测试"""


def _setup_scores(client, sample_student, sample_exam):
    """辅助函数：录入全科成绩"""
    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()

    scores_map = {
        "语文": 120, "数学": 135, "英语": 110,
        "物理": 85, "化学": 80, "生物": 78,
        "思想政治": 75, "地理": 82,
    }
    for subj_name, score in scores_map.items():
        es = next(s for s in subjects if s["subject"] == subj_name)
        client.post("/api/scores/entry", json={
            "student_id": sample_student.id,
            "exam_subject_id": es["id"],
            "raw_score": float(score),
        })

    # 触发赋分
    for subj_name in ["化学", "生物", "思想政治", "地理"]:
        es = next(s for s in subjects if s["subject"] == subj_name)
        client.post(f"/api/scores/convert/{es['id']}")


def test_subject_stats(client, sample_student, sample_exam):
    """单科统计"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    yuwen = next(s for s in subjects if s["subject"] == "语文")

    resp = client.get(f"/api/analysis/subject/{yuwen['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject"] == "语文"
    assert data["average"] > 0
    assert "pass_rate" in data
    assert "excellent_rate" in data


def test_score_distribution(client, sample_student, sample_exam):
    """分数段分布"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/scores/exam-subject/{sample_exam.id}")
    subjects = resp.json()
    yuwen = next(s for s in subjects if s["subject"] == "语文")

    resp = client.get(f"/api/analysis/distribution/{yuwen['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert "labels" in data
    assert "counts" in data
    assert len(data["labels"]) > 0


def test_grade_overview(client, sample_student, sample_exam):
    """年级总览"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/analysis/grade/{sample_exam.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "subjects" in data
    assert "total" in data


def test_class_comparison(client, sample_student, sample_exam):
    """班级对比"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/analysis/class-comparison/{sample_exam.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "class_name" in data[0]
    assert "subjects" in data[0]


def test_student_trend(client, sample_student, sample_exam):
    """学生纵向趋势"""
    _setup_scores(client, sample_student, sample_exam)

    resp = client.get(f"/api/analysis/student-trend/{sample_student.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert "exam_name" in data[0]
    assert "scores" in data[0]
    assert "total" in data[0]
```

- [ ] **Step 2: 运行所有测试**

```bash
python -m pytest tests/ -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_analysis.py
git commit -m "test: add statistics and analysis API tests"
```

---

## 阶段 2：安全 + 性能

### Task 10: 用户认证模型与登录页面

**Files:**
- Create: `app/models/user.py`
- Modify: `app/models/__init__.py`
- Modify: `app/main.py`
- Modify: `app/config.py`

- [ ] **Step 1: 创建 User 模型**

```python
"""用户认证模型"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: 更新 models/__init__.py**

```python
from app.models.student import ClassGroup, Student
from app.models.exam import Exam, ExamSubject
from app.models.score import Score, ConversionRule
from app.models.user import User

__all__ = ["ClassGroup", "Student", "Exam", "ExamSubject", "Score", "ConversionRule", "User"]
```

- [ ] **Step 3: 更新 config.py — 添加 session 相关配置**

```python
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'scores.db')}"
CONVERSION_RULES_PATH = os.path.join(BASE_DIR, "data", "conversion_rules.json")

SECRET_KEY = os.environ.get("GRADE_SECRET_KEY", "jiangsu-gaokao-grade-analysis-2026")
SESSION_MAX_AGE = 86400  # 24 hours
```

- [ ] **Step 4: Commit**

```bash
git add app/models/user.py app/models/__init__.py app/config.py
git commit -m "feat: add User model for authentication"
```

### Task 11: 认证服务与路由

**Files:**
- Create: `app/routers/auth.py`
- Modify: `app/main.py`
- Modify: `app/templates/base.html`

- [ ] **Step 1: 创建认证路由**

```python
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
        raise RedirectException("/login")
    return user


class RedirectException(Exception):
    def __init__(self, url: str):
        self.url = url


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
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
```

- [ ] **Step 2: 创建登录模板 templates/auth/login.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>登录 - 成绩分析系统</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; }
        .login-card { max-width: 400px; margin: 0 auto; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
    </style>
</head>
<body>
    <div class="container">
        <div class="card login-card">
            <div class="card-body p-5">
                <h4 class="text-center mb-4">成绩分析系统</h4>
                {% if error %}
                <div class="alert alert-danger">{{ error }}</div>
                {% endif %}
                <form method="post" action="/login">
                    <div class="mb-3">
                        <label class="form-label">用户名</label>
                        <input type="text" name="username" class="form-control" required autofocus>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">密码</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">登录</button>
                </form>
            </div>
        </div>
    </div>
</body>
</html>
```

- [ ] **Step 3: 更新 main.py — 添加 session 中间件和认证路由**

在 `app/main.py` 中添加：

```python
from starlette.middleware.sessions import SessionMiddleware
from app.config import SECRET_KEY, SESSION_MAX_AGE
from app.routers import auth

# 在 app 创建后添加
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=SESSION_MAX_AGE)
app.include_router(auth.router, tags=["认证"])
```

- [ ] **Step 4: Commit**

```bash
git add app/routers/auth.py app/templates/auth/login.html app/main.py
git commit -m "feat: add login/logout authentication with session middleware"
```

### Task 12: 路由保护 — 全局登录检查

**Files:**
- Modify: `app/routers/pages.py`
- Modify: `app/routers/students.py`
- Modify: `app/routers/exams.py`
- Modify: `app/routers/scores.py`
- Modify: `app/routers/analysis.py`
- Modify: `app/main.py`

- [ ] **Step 1: 在 main.py 中添加全局认证异常处理**

```python
from fastapi.responses import RedirectResponse

@app.exception_handler(auth.RedirectException)
async def redirect_handler(request: Request, exc: auth.RedirectException):
    return RedirectResponse(exc.url)
```

- [ ] **Step 2: 更新 pages.py — 所有页面路由添加 require_user 依赖**

```python
from app.routers.auth import require_user

# 每个页面路由添加 current_user: User = Depends(require_user)
```

- [ ] **Step 3: 更新 API 路由 — 添加 get_current_user 依赖**

在 `students.py`, `exams.py`, `scores.py`, `analysis.py` 的每个路由函数添加：
```python
from app.routers.auth import get_current_user
from app.models.user import User

# 添加参数: current_user: User = Depends(get_current_user)
```

- [ ] **Step 4: 添加默认管理员账户**

在 `app/main.py` 的 lifespan 中添加初始化逻辑：

```python
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
```

- [ ] **Step 5: Commit**

```bash
git add app/routers/ app/main.py
git commit -m "feat: add route protection, default admin user creation"
```

### Task 13: 修复 N+1 查询 — score_service.py

**Files:**
- Modify: `app/services/score_service.py`

- [ ] **Step 1: 重写 get_exam_all_totals**

```python
def get_exam_all_totals(db: Session, exam_id: int) -> list[dict]:
    """计算某次考试所有学生的总分（优化：单次查询）"""
    from app.models.student import Student

    students = db.query(Student).all()
    if not students:
        return []

    # 一次性获取该考试所有科目信息
    exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()
    es_map = {es.subject: es for es in exam_subjects}
    es_ids = [es.id for es in exam_subjects]

    # 一次性获取所有成绩
    all_scores = (
        db.query(Score)
        .filter(Score.exam_subject_id.in_(es_ids))
        .all()
    )
    # 建立 (student_id, exam_subject_id) -> Score 的映射
    score_map = {}
    for s in all_scores:
        score_map[(s.student_id, s.exam_subject_id)] = s

    results = []
    for stu in students:
        scores_detail = {}
        total = 0.0

        # 3科必考
        for subj in ["语文", "数学", "英语"]:
            if subj in es_map:
                score = score_map.get((stu.id, es_map[subj].id))
                if score:
                    scores_detail[subj] = score.raw_score
                    total += score.raw_score

        # "1"选科
        pref = stu.preferred_subject
        if pref in es_map:
            score = score_map.get((stu.id, es_map[pref].id))
            if score:
                scores_detail[pref] = score.raw_score
                total += score.raw_score

        # "2"赋分科目
        for elec in [stu.elective_1, stu.elective_2]:
            if elec in es_map:
                score = score_map.get((stu.id, es_map[elec].id))
                if score:
                    val = score.converted_score if score.converted_score is not None else score.raw_score
                    scores_detail[elec] = val
                    total += val

        if scores_detail:
            results.append({
                "student_id": stu.id,
                "student_name": stu.name,
                "scores": scores_detail,
                "total": round(total, 1),
            })

    results.sort(key=lambda x: x["total"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results
```

- [ ] **Step 2: Commit**

```bash
git add app/services/score_service.py
git commit -m "perf: fix N+1 query in get_exam_all_totals with batch loading"
```

### Task 14: 修复 N+1 查询 — stats_service.py

**Files:**
- Modify: `app/services/stats_service.py`

- [ ] **Step 1: 重写 class_comparison**

```python
def class_comparison(db: Session, exam_id: int) -> list[dict]:
    """班级对比：每个班级各科均分和总分均分（优化：批量查询）"""
    classes = db.query(ClassGroup).all()
    exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()

    if not classes or not exam_subjects:
        return []

    # 建立学生 -> 班级映射
    students = db.query(Student).all()
    student_class_map = {s.id: s.class_id for s in students}
    class_students = {}  # class_id -> [student_ids]
    for s in students:
        class_students.setdefault(s.class_id, []).append(s.id)

    # 一次性获取所有成绩
    es_ids = [es.id for es in exam_subjects]
    all_scores = (
        db.query(Score)
        .filter(Score.exam_subject_id.in_(es_ids))
        .all()
    )

    # 按 (class_id, subject) 聚合
    class_subject_values = {}  # (class_id, subject) -> [values]
    for score in all_scores:
        cls_id = student_class_map.get(score.student_id)
        if cls_id is None:
            continue
        es = next((e for e in exam_subjects if e.id == score.exam_subject_id), None)
        if not es:
            continue
        key = (cls_id, es.subject)
        val = score.converted_score if (es.needs_conversion and score.converted_score is not None) else score.raw_score
        class_subject_values.setdefault(key, []).append(val)

    result = []
    for cls in classes:
        sids = class_students.get(cls.id, [])
        if not sids:
            continue

        cls_data = {"class_name": cls.name, "student_count": len(sids), "subjects": {}}
        for es in exam_subjects:
            values = class_subject_values.get((cls.id, es.subject), [])
            if values:
                cls_data["subjects"][es.subject] = round(sum(values) / len(values), 1)

        result.append(cls_data)

    return result
```

- [ ] **Step 2: Commit**

```bash
git add app/services/stats_service.py
git commit -m "perf: fix N+1 query in class_comparison with batch loading"
```

### Task 15: API 分页

**Files:**
- Modify: `app/routers/students.py`
- Modify: `app/routers/exams.py`

- [ ] **Step 1: 更新 students.py 列表 API**

```python
from fastapi import Query

@router.get("/")
def list_students(
    class_id: int = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Student)
    if class_id:
        q = q.filter(Student.class_id == class_id)
    total = q.count()
    students = q.offset(skip).limit(limit).all()
    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "student_no": s.student_no,
                "class_id": s.class_id,
                "class_name": s.class_group.name,
                "preferred_subject": s.preferred_subject,
                "elective_1": s.elective_1,
                "elective_2": s.elective_2,
            }
            for s in students
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }
```

- [ ] **Step 2: 更新 exams.py 列表 API**

```python
@router.get("/")
def list_exams(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Exam).order_by(Exam.exam_date.desc())
    total = q.count()
    exams = q.offset(skip).limit(limit).all()
    return {
        "items": [
            {
                "id": e.id,
                "name": e.name,
                "exam_date": str(e.exam_date),
                "exam_type": e.exam_type,
                "subject_count": len(e.subjects),
            }
            for e in exams
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }
```

- [ ] **Step 3: 更新前端模板中的列表 API 调用**

需要更新 `index.html`、`students/list.html`、`exams/list.html` 等模板中的 fetch 调用，适配新的分页响应格式。

- [ ] **Step 4: Commit**

```bash
git add app/routers/students.py app/routers/exams.py app/templates/
git commit -m "feat: add pagination to student and exam list APIs"
```

---

## 阶段 3：现代仪表盘 UI 升级

### Task 16: 公共静态资源 — CSS 和 JS 工具

**Files:**
- Create: `static/css/main.css`
- Create: `static/js/utils.js`

- [ ] **Step 1: 创建 static/css/main.css**

```css
:root {
    --primary: #4A90D9;
    --success: #67C23A;
    --warning: #E6A23C;
    --danger: #F56C6C;
    --sidebar-width: 240px;
    --sidebar-collapsed: 64px;
    --sidebar-bg-start: #1a1a2e;
    --sidebar-bg-end: #16213e;
    --bg-main: #f5f7fa;
    --card-shadow: 0 2px 12px rgba(0,0,0,0.08);
}

body {
    background: var(--bg-main);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* Sidebar */
.sidebar {
    position: fixed; top: 0; left: 0; bottom: 0;
    width: var(--sidebar-width);
    background: linear-gradient(180deg, var(--sidebar-bg-start), var(--sidebar-bg-end));
    color: #fff; z-index: 100; overflow-y: auto;
    transition: width 0.3s ease;
}
.sidebar .logo {
    padding: 20px 16px; font-size: 16px; font-weight: 600;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    white-space: nowrap; display: flex; align-items: center; gap: 10px;
}
.sidebar .nav-link {
    color: rgba(255,255,255,0.65); padding: 10px 24px;
    font-size: 14px; transition: all 0.2s; border-radius: 0 20px 20px 0;
    margin-right: 8px;
}
.sidebar .nav-link:hover { color: #fff; background: rgba(255,255,255,0.08); }
.sidebar .nav-link.active { color: #fff; background: var(--primary); }
.sidebar .nav-link i { margin-right: 10px; width: 18px; text-align: center; }
.sidebar .nav-section {
    padding: 16px 24px 6px; font-size: 11px;
    color: rgba(255,255,255,0.35); text-transform: uppercase; letter-spacing: 1.5px;
}

/* Main content */
.main-content { margin-left: var(--sidebar-width); padding: 24px; min-height: 100vh; }

/* Top bar */
.top-bar {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px; padding-bottom: 16px;
    border-bottom: 1px solid #e8e8e8;
}
.top-bar .breadcrumb { margin: 0; font-size: 13px; }
.top-bar .user-info { display: flex; align-items: center; gap: 12px; }

/* Cards */
.card {
    border: none; border-radius: 10px;
    box-shadow: var(--card-shadow);
    transition: transform 0.2s, box-shadow 0.2s;
}
.card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
.card-header {
    background: transparent; border-bottom: 1px solid #f0f0f0;
    font-weight: 600; font-size: 15px; padding: 16px 20px;
}
.card-body { padding: 20px; }

/* Stat cards */
.stat-card { padding: 20px; }
.stat-card .stat-icon {
    width: 48px; height: 48px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; margin-bottom: 12px;
}
.stat-card .stat-value { font-size: 28px; font-weight: 700; color: #1a1a2e; }
.stat-card .stat-label { font-size: 13px; color: #8c8c8c; margin-top: 4px; }
.stat-card .stat-trend { font-size: 12px; margin-top: 4px; }
.stat-card .stat-trend.up { color: var(--success); }
.stat-card .stat-trend.down { color: var(--danger); }

/* Tables */
.table { font-size: 14px; }
.table thead th {
    background: #fafafa; border-bottom: 2px solid #e8e8e8;
    font-weight: 600; color: #555; white-space: nowrap;
}
.table-hover tbody tr:hover { background: #f0f7ff; }

/* Buttons */
.btn { border-radius: 6px; font-size: 14px; }
.btn-primary { background: var(--primary); border-color: var(--primary); }
.btn-primary:hover { background: #3a7bc8; border-color: #3a7bc8; }

/* Toast container */
.toast-container { position: fixed; top: 20px; right: 20px; z-index: 9999; }

/* Skeleton loading */
.skeleton {
    background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
    background-size: 200% 100%;
    animation: skeleton-loading 1.5s infinite;
    border-radius: 4px;
}
@keyframes skeleton-loading {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
```

- [ ] **Step 2: 创建 static/js/utils.js**

```javascript
/**
 * 通用工具函数
 */

// Toast 通知
function showToast(message, type = 'success') {
    const container = document.querySelector('.toast-container') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0 show`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    container.appendChild(toast);
    if (type === 'success') {
        setTimeout(() => toast.remove(), 3000);
    }
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

// 统一 fetch 封装
async function apiFetch(url, options = {}) {
    try {
        const resp = await fetch(url, options);
        if (resp.status === 303 || resp.redirected) {
            window.location.href = resp.url;
            return null;
        }
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: '请求失败' }));
            showToast(err.detail || '请求失败', 'danger');
            throw new Error(err.detail);
        }
        return await resp.json();
    } catch (e) {
        if (e.message !== '请求失败') {
            showToast('网络错误，请检查连接', 'danger');
        }
        throw e;
    }
}

// 确认对话框
function confirmDelete(message = '确定要删除吗？此操作不可撤销。') {
    return new Promise(resolve => {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-sm modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-body text-center py-4">
                        <i class="bi bi-exclamation-triangle text-warning" style="font-size:48px;"></i>
                        <p class="mt-3 mb-0">${message}</p>
                    </div>
                    <div class="modal-footer justify-content-center">
                        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-danger btn-sm" id="confirmBtn">确认删除</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        modal.querySelector('#confirmBtn').onclick = () => { bsModal.hide(); resolve(true); };
        modal.addEventListener('hidden.bs.modal', () => { modal.remove(); resolve(false); });
    });
}

// 分数格式化
function formatScore(score) {
    if (score === null || score === undefined) return '-';
    return Number(score).toFixed(1);
}

// 百分比格式化
function formatPercent(value) {
    return value.toFixed(1) + '%';
}
```

- [ ] **Step 3: Commit**

```bash
git add static/css/main.css static/js/utils.js
git commit -m "feat: add global CSS theme and JS utility functions"
```

### Task 17: 更新 base.html — 现代仪表盘布局

**Files:**
- Modify: `app/templates/base.html`

- [ ] **Step 1: 重写 base.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}成绩分析系统{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <link href="/static/css/main.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
    {% block extra_head %}{% endblock %}
</head>
<body>
    <!-- Sidebar -->
    <div class="sidebar">
        <div class="logo">
            <i class="bi bi-mortarboard-fill"></i>
            <span>成绩分析系统</span>
        </div>
        <nav class="nav flex-column mt-2">
            <div class="nav-section">概览</div>
            <a class="nav-link {% if request.url.path == '/' %}active{% endif %}" href="/">
                <i class="bi bi-speedometer2"></i> 仪表盘
            </a>

            <div class="nav-section">数据管理</div>
            <a class="nav-link {% if '/students' in request.url.path %}active{% endif %}" href="/students">
                <i class="bi bi-people"></i> 学生管理
            </a>
            <a class="nav-link {% if '/exams' in request.url.path %}active{% endif %}" href="/exams">
                <i class="bi bi-journal-text"></i> 考试管理
            </a>
            <a class="nav-link {% if '/scores/entry' in request.url.path %}active{% endif %}" href="/scores/entry">
                <i class="bi bi-pencil-square"></i> 成绩录入
            </a>

            <div class="nav-section">统计分析</div>
            <a class="nav-link {% if '/analysis/grade' in request.url.path %}active{% endif %}" href="/analysis/grade">
                <i class="bi bi-bar-chart"></i> 年级分析
            </a>
            <a class="nav-link {% if '/analysis/class' in request.url.path %}active{% endif %}" href="/analysis/class">
                <i class="bi bi-diagram-3"></i> 班级对比
            </a>
            <a class="nav-link {% if '/analysis/subject' in request.url.path %}active{% endif %}" href="/analysis/subject">
                <i class="bi bi-book"></i> 学科分析
            </a>
            <a class="nav-link {% if '/analysis/longitudinal' in request.url.path %}active{% endif %}" href="/analysis/longitudinal">
                <i class="bi bi-graph-up"></i> 纵向追踪
            </a>
        </nav>
    </div>

    <!-- Main content -->
    <div class="main-content">
        <div class="top-bar">
            <nav aria-label="breadcrumb">
                <ol class="breadcrumb">
                    <li class="breadcrumb-item"><a href="/" class="text-decoration-none">首页</a></li>
                    {% block breadcrumb %}{% endblock %}
                </ol>
            </nav>
            <div class="user-info">
                <span class="text-muted"><i class="bi bi-person-circle"></i> {{ request.session.get('username', 'admin') }}</span>
                <a href="/logout" class="btn btn-outline-secondary btn-sm"><i class="bi bi-box-arrow-right"></i> 登出</a>
            </div>
        </div>

        {% block content %}{% endblock %}
    </div>

    <!-- Toast container -->
    <div class="toast-container"></div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/js/utils.js"></script>
    {% block extra_scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/base.html
git commit -m "feat: modernize base layout with top bar, breadcrumbs, toast support"
```

### Task 18: Dashboard 首页升级

**Files:**
- Modify: `app/templates/index.html`

- [ ] **Step 1: 重写 index.html**

```html
{% extends "base.html" %}
{% block title %}仪表盘 - 成绩分析系统{% endblock %}
{% block breadcrumb %}<li class="breadcrumb-item active">仪表盘</li>{% endblock %}

{% block content %}
<!-- Stats Cards -->
<div class="row g-3 mb-4">
    <div class="col-md-3">
        <div class="card stat-card">
            <div class="stat-icon" style="background:rgba(74,144,217,0.1);color:#4A90D9;">
                <i class="bi bi-people"></i>
            </div>
            <div class="stat-value" id="stat-students">-</div>
            <div class="stat-label">学生总数</div>
            <div class="stat-trend" id="stat-classes-info">-</div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card stat-card">
            <div class="stat-icon" style="background:rgba(103,194,58,0.1);color:#67C23A;">
                <i class="bi bi-journal-text"></i>
            </div>
            <div class="stat-value" id="stat-exams">-</div>
            <div class="stat-label">考试次数</div>
            <div class="stat-trend" id="stat-latest-info">-</div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card stat-card">
            <div class="stat-icon" style="background:rgba(230,162,60,0.1);color:#E6A23C;">
                <i class="bi bi-award"></i>
            </div>
            <div class="stat-value" id="stat-avg-score">-</div>
            <div class="stat-label">最新考试平均分</div>
            <div class="stat-trend" id="stat-score-range">-</div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card stat-card">
            <div class="stat-icon" style="background:rgba(245,108,108,0.1);color:#F56C6C;">
                <i class="bi bi-check-circle"></i>
            </div>
            <div class="stat-value" id="stat-pass-rate">-</div>
            <div class="stat-label">最新考试及格率</div>
        </div>
    </div>
</div>

<!-- Charts Row -->
<div class="row g-3 mb-4">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header"><i class="bi bi-bullseye me-2"></i>学科平均分雷达图</div>
            <div class="card-body">
                <div id="chart-radar" style="height: 320px;"></div>
            </div>
        </div>
    </div>
    <div class="col-md-6">
        <div class="card">
            <div class="card-header"><i class="bi bi-bar-chart me-2"></i>班级总分对比</div>
            <div class="card-body">
                <div id="chart-class-bar" style="height: 320px;"></div>
            </div>
        </div>
    </div>
</div>

<!-- Quick Actions -->
<div class="row g-3">
    <div class="col-12">
        <div class="card">
            <div class="card-header"><i class="bi bi-lightning me-2"></i>快速操作</div>
            <div class="card-body d-flex flex-wrap gap-2">
                <a href="/scores/entry" class="btn btn-primary"><i class="bi bi-pencil-square me-1"></i> 成绩录入</a>
                <a href="/students" class="btn btn-outline-primary"><i class="bi bi-people me-1"></i> 学生管理</a>
                <a href="/exams" class="btn btn-outline-primary"><i class="bi bi-journal-plus me-1"></i> 考试管理</a>
                <a href="/analysis/grade" class="btn btn-outline-primary"><i class="bi bi-bar-chart me-1"></i> 年级分析</a>
                <a href="/analysis/class" class="btn btn-outline-primary"><i class="bi bi-diagram-3 me-1"></i> 班级对比</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
const COLORS = ['#4A90D9', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#b37feb', '#36cfc9', '#ff85c0', '#ffc53d'];

async function loadDashboard() {
    try {
        const [studentsData, classes, examsData] = await Promise.all([
            apiFetch('/api/students/'),
            apiFetch('/api/students/classes'),
            apiFetch('/api/exams/'),
        ]);

        const students = studentsData.items || studentsData;
        const exams = examsData.items || examsData;

        document.getElementById('stat-students').textContent = students.length;
        document.getElementById('stat-classes-info').textContent = `${classes.length} 个班级`;
        document.getElementById('stat-exams').textContent = exams.length;

        if (exams.length > 0) {
            document.getElementById('stat-latest-info').textContent = `最近: ${exams[0].name}`;
            // 加载最新考试数据
            loadLatestExamStats(exams[0].id);
        } else {
            document.getElementById('stat-latest-info').textContent = '暂无考试';
        }
    } catch (e) {
        console.error('加载仪表盘失败:', e);
    }
}

async function loadLatestExamStats(examId) {
    try {
        const [gradeData, classData] = await Promise.all([
            apiFetch(`/api/analysis/grade/${examId}`),
            apiFetch(`/api/analysis/class-comparison/${examId}`),
        ]);

        // 平均分
        if (gradeData.total && gradeData.total.average) {
            document.getElementById('stat-avg-score').textContent = gradeData.total.average;
            document.getElementById('stat-score-range').textContent =
                `最高 ${gradeData.total.max} / 最低 ${gradeData.total.min}`;
        }

        // 及格率（取语文及格率作为代表）
        if (gradeData.subjects && gradeData.subjects['语文']) {
            document.getElementById('stat-pass-rate').textContent =
                gradeData.subjects['语文'].pass_rate + '%';
        }

        // 雷达图
        if (gradeData.subjects) {
            renderRadar(gradeData.subjects);
        }

        // 班级对比柱状图
        if (classData && classData.length > 0) {
            renderClassBar(classData);
        }
    } catch (e) {
        console.error('加载考试统计失败:', e);
    }
}

function renderRadar(subjects) {
    const chart = echarts.init(document.getElementById('chart-radar'));
    const names = Object.keys(subjects).filter(s => s !== '物理' && s !== '历史');
    const values = names.map(n => subjects[n].average);
    const maxValues = names.map(n => subjects[n].full_score);

    chart.setOption({
        tooltip: {},
        radar: {
            indicator: names.map((name, i) => ({ name, max: maxValues[i] })),
            radius: '65%',
        },
        series: [{
            type: 'radar',
            data: [{
                value: values,
                name: '平均分',
                areaStyle: { opacity: 0.15 },
                lineStyle: { color: '#4A90D9' },
                itemStyle: { color: '#4A90D9' },
            }],
        }],
    });
}

function renderClassBar(classData) {
    const chart = echarts.init(document.getElementById('chart-class-bar'));
    const classNames = classData.map(c => c.class_name);
    const subjects = Object.keys(classData[0].subjects || {});

    const series = subjects.map((subj, i) => ({
        name: subj,
        type: 'bar',
        data: classData.map(c => c.subjects[subj] || 0),
        itemStyle: { color: COLORS[i % COLORS.length] },
    }));

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: subjects, bottom: 0, type: 'scroll' },
        grid: { left: 50, right: 20, top: 20, bottom: 50 },
        xAxis: { type: 'category', data: classNames },
        yAxis: { type: 'value' },
        series,
    });
}

loadDashboard();
</script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: upgrade dashboard with stat cards, radar chart, class comparison bar"
```

### Task 19: 学生列表页面升级

**Files:**
- Modify: `app/templates/students/list.html`

- [ ] **Step 1: 重写学生列表页面**

适配分页 API，添加表格搜索、分页控件、删除确认对话框。

- [ ] **Step 2: Commit**

```bash
git add app/templates/students/list.html
git commit -m "feat: upgrade student list with search, pagination, delete confirmation"
```

### Task 20: 考试列表和详情页面升级

**Files:**
- Modify: `app/templates/exams/list.html`
- Modify: `app/templates/exams/detail.html`

- [ ] **Step 1: 升级考试列表页面**

适配分页 API，添加删除确认。

- [ ] **Step 2: 升级考试详情页面**

统一图表配色，优化排名表格。

- [ ] **Step 3: Commit**

```bash
git add app/templates/exams/
git commit -m "feat: upgrade exam list and detail pages with modern styling"
```

### Task 21: 分析页面升级

**Files:**
- Modify: `app/templates/analysis/grade.html`
- Modify: `app/templates/analysis/class.html`
- Modify: `app/templates/analysis/subject.html`
- Modify: `app/templates/analysis/longitudinal.html`

- [ ] **Step 1: 升级所有分析页面**

统一使用新 CSS 变量和配色，优化图表交互。

- [ ] **Step 2: Commit**

```bash
git add app/templates/analysis/
git commit -m "feat: upgrade analysis pages with unified chart theming"
```

### Task 22: 成绩录入页面升级

**Files:**
- Modify: `app/templates/scores/entry.html`

- [ ] **Step 1: 升级成绩录入页面**

优化表格样式，添加 loading 状态，使用 apiFetch。

- [ ] **Step 2: Commit**

```bash
git add app/templates/scores/entry.html
git commit -m "feat: upgrade score entry page with modern styling"
```

### Task 23: 最终验证

- [ ] **Step 1: 运行所有测试**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 2: 启动服务器手动验证**

```bash
python run.py
```

访问 http://localhost:8000 验证：
- 登录页面显示
- 登录后进入仪表盘
- 所有页面正常加载
- 图表正常显示
- 增删改查功能正常

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```
