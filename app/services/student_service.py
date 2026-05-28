"""
学生管理服务：CRUD、搜索、分页、批量操作、班级管理
"""

import re
import math
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func, or_

from app.models.student import Student, ClassGroup
from app.models.exam import Exam, ExamSubject
from app.models.score import Score
from app.constants import (
    VALID_COMBINATIONS, COMBINATION_SUBJECTS, ALL_SUBJECTS,
    CONVERSION_SUBJECTS, STUDENT_NO_PATTERN, STUDENT_NO_ERROR_MSG,
)


# ---- 学号校验 ----

def validate_student_no(student_no: str) -> tuple[bool, str]:
    """校验学号格式，返回 (是否合法, 错误信息)"""
    if not re.match(STUDENT_NO_PATTERN, student_no):
        return False, STUDENT_NO_ERROR_MSG
    return True, ""


# ---- 班级 ----

def list_classes(db: Session) -> list[dict]:
    classes = db.query(ClassGroup).all()
    return [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes]


def list_classes_with_students(db: Session) -> list[dict]:
    """返回有学生的班级"""
    classes = (
        db.query(ClassGroup)
        .join(Student, Student.class_id == ClassGroup.id)
        .distinct()
        .all()
    )
    return [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes]



# ---- 组合信息 ----

def list_combinations() -> list[dict]:
    return [
        {"name": name, "subjects": subjects}
        for name, subjects in COMBINATION_SUBJECTS.items()
    ]


def list_available_combinations(db: Session) -> list[str]:
    combos = (
        db.query(Student.combination)
        .filter(Student.combination != None, Student.combination != "")
        .distinct()
        .all()
    )
    return sorted([c[0] for c in combos])


def list_available_enrollment_years(db: Session) -> list[int]:
    """返回数据库中实际使用的入学年份列表"""
    years = (
        db.query(Student.enrollment_year)
        .filter(Student.enrollment_year != None)
        .distinct()
        .all()
    )
    return sorted([y[0] for y in years], reverse=True)


# ---- 学生 CRUD ----

SORT_FIELDS_MAP = {
    "student_no": lambda: Student.student_no,
    "name": lambda: Student.name,
    "class_name": lambda: ClassGroup.name,
    "combination": lambda: Student.combination,
    "enrollment_year": lambda: Student.enrollment_year,
}

SCORE_FIELDS = {"语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"}


def list_students(
    db: Session,
    class_id: int | None = None,
    original_class_id: int | None = None,
    enrollment_year: int | None = None,
    combination: str | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """返回分页的学生列表，含最新考试成绩"""
    q = db.query(Student).join(ClassGroup, Student.class_id == ClassGroup.id)
    if class_id:
        q = q.filter(Student.class_id == class_id)
    if original_class_id:
        q = q.filter(Student.original_class_id == original_class_id)
    if enrollment_year:
        q = q.filter(Student.enrollment_year == enrollment_year)
    if combination:
        q = q.filter(Student.combination == combination)
    if search:
        q = q.filter(or_(
            Student.name.contains(search),
            Student.student_no.contains(search),
        ))

    # 总数
    total = q.count()

    # 排序（仅对数据库字段排序）
    sort_field_fn = SORT_FIELDS_MAP.get(sort_by)
    if sort_field_fn:
        col = sort_field_fn()
        q = q.order_by(desc(col) if sort_order == "desc" else asc(col))
    else:
        q = q.order_by(Student.student_no)

    # 分页
    pages = max(1, math.ceil(total / page_size))
    students = q.offset((page - 1) * page_size).limit(page_size).all()

    # 获取最新一次考试的成绩
    latest_exam = db.query(Exam).order_by(Exam.exam_date.desc(), Exam.id.desc()).first()
    score_map = {}
    exam_subjects = []
    if latest_exam:
        exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == latest_exam.id).all()
        es_ids = [es.id for es in exam_subjects]
        if es_ids:
            all_scores = db.query(Score).filter(Score.exam_subject_id.in_(es_ids)).all()
            for sc in all_scores:
                score_map[(sc.student_id, sc.exam_subject_id)] = sc

    items = []
    for s in students:
        item = {
            "id": s.id,
            "name": s.name,
            "student_no": s.student_no,
            "class_id": s.class_id,
            "class_name": s.class_group.name,
            "original_class_id": s.original_class_id,
            "original_class_name": s.original_class_group.name if s.original_class_group else "",
            "combination": s.combination or "",
            "id_card": s.id_card or "",
            "enrollment_year": s.enrollment_year,
            "gender": s.gender or "",
        }
        if latest_exam:
            for es in exam_subjects:
                sc = score_map.get((s.id, es.id))
                if sc:
                    val = sc.converted_score if (es.subject in CONVERSION_SUBJECTS and sc.converted_score is not None) else sc.raw_score
                    item[es.subject] = val
                else:
                    item[es.subject] = None
        items.append(item)

    # 科目排序（内存排序）
    if sort_by in SCORE_FIELDS:
        reverse = sort_order == "desc"
        items.sort(key=lambda x: (x.get(sort_by) is None, x.get(sort_by) or 0), reverse=reverse)

    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


def get_student(db: Session, student_id: int) -> dict:
    s = db.get(Student, student_id)
    if not s:
        raise ValueError("学生不存在")
    return {
        "id": s.id,
        "name": s.name,
        "student_no": s.student_no,
        "class_id": s.class_id,
        "class_name": s.class_group.name,
        "original_class_id": s.original_class_id,
        "original_class_name": s.original_class_group.name if s.original_class_group else "",
        "combination": s.combination or "",
        "id_card": s.id_card or "",
        "enrollment_year": s.enrollment_year,
        "gender": s.gender or "",
    }


def create_student(db: Session, name: str, student_no: str, class_id: int, combination: str = "", id_card: str = "", gender: str = "") -> dict:
    # 学号格式校验
    valid, msg = validate_student_no(student_no)
    if not valid:
        raise ValueError(msg)
    if db.query(Student).filter(Student.student_no == student_no).first():
        raise ValueError("学号已存在")
    combo = combination.strip()
    if combo and combo not in VALID_COMBINATIONS:
        raise ValueError(f"无效的选科组合: {combo}")
    # 身份证号唯一性校验
    if id_card and id_card.strip():
        if db.query(Student).filter(Student.id_card == id_card.strip()).first():
            raise ValueError("身份证号已存在")
    stu = Student(
        name=name,
        student_no=student_no,
        class_id=class_id,
        combination=combo,
        id_card=id_card.strip() if id_card else None,
        gender=gender.strip() if gender else "",
    )
    db.add(stu)
    db.commit()
    db.refresh(stu)
    return {"id": stu.id, "name": stu.name, "student_no": stu.student_no}


def update_student(db: Session, student_id: int, data: dict) -> dict:
    stu = db.get(Student, student_id)
    if not stu:
        raise ValueError("学生不存在")
    if "name" in data and data["name"] is not None:
        stu.name = data["name"]
    if "student_no" in data and data["student_no"] is not None:
        valid, msg = validate_student_no(data["student_no"])
        if not valid:
            raise ValueError(msg)
        existing = db.query(Student).filter(Student.student_no == data["student_no"], Student.id != student_id).first()
        if existing:
            raise ValueError("学号已存在")
        stu.student_no = data["student_no"]
    if "class_id" in data and data["class_id"] is not None:
        stu.class_id = data["class_id"]
    if "combination" in data and data["combination"] is not None:
        combo = data["combination"].strip()
        if combo and combo not in VALID_COMBINATIONS:
            raise ValueError(f"无效的选科组合: {combo}")
        stu.combination = combo
    if "id_card" in data and data["id_card"] is not None:
        id_card = data["id_card"].strip()
        if id_card:
            existing = db.query(Student).filter(Student.id_card == id_card, Student.id != student_id).first()
            if existing:
                raise ValueError("身份证号已存在")
        stu.id_card = id_card if id_card else None
    if "gender" in data and data["gender"] is not None:
        stu.gender = data["gender"].strip()
    if "enrollment_year" in data and data["enrollment_year"] is not None:
        stu.enrollment_year = data["enrollment_year"]
    db.commit()
    db.refresh(stu)
    return {"id": stu.id, "name": stu.name, "student_no": stu.student_no}


def delete_student(db: Session, student_id: int) -> dict:
    stu = db.get(Student, student_id)
    if not stu:
        raise ValueError("学生不存在")
    db.delete(stu)
    db.commit()
    return {"ok": True}


def get_student_score_count(db: Session, student_id: int) -> int:
    """获取学生的成绩记录数量"""
    return db.query(Score).filter(Score.student_id == student_id).count()


# ---- 批量操作 ----

def batch_delete_students(db: Session, student_ids: list[int]) -> dict:
    deleted = 0
    errors = []
    for sid in student_ids:
        stu = db.get(Student, sid)
        if stu:
            db.delete(stu)
            deleted += 1
        else:
            errors.append(f"学生 ID {sid} 不存在")
    db.commit()
    return {"deleted": deleted, "errors": errors}


def batch_update_class(db: Session, student_ids: list[int], class_id: int) -> dict:
    target = db.get(ClassGroup, class_id)
    if not target:
        raise ValueError("目标班级不存在")
    updated = 0
    for sid in student_ids:
        stu = db.get(Student, sid)
        if stu:
            stu.class_id = class_id
            updated += 1
    db.commit()
    return {"updated": updated}


def batch_update_combination(db: Session, student_ids: list[int], combination: str) -> dict:
    combo = combination.strip()
    if combo and combo not in VALID_COMBINATIONS:
        raise ValueError(f"无效的选科组合: {combo}")
    updated = 0
    for sid in student_ids:
        stu = db.get(Student, sid)
        if stu:
            stu.combination = combo
            updated += 1
    db.commit()
    return {"updated": updated}


def batch_update_students(db: Session, student_ids: list[int], data: dict) -> dict:
    """批量更新学生信息（学号、班级、原班级），不影响成绩记录"""
    updated = 0
    errors = []
    for sid in student_ids:
        stu = db.get(Student, sid)
        if not stu:
            errors.append(f"学生 ID {sid} 不存在")
            continue
        if "student_no" in data and data["student_no"] is not None:
            valid, msg = validate_student_no(data["student_no"])
            if not valid:
                errors.append(f"学生 ID {sid}: {msg}")
                continue
            existing = db.query(Student).filter(Student.student_no == data["student_no"], Student.id != sid).first()
            if existing:
                errors.append(f"学生 ID {sid}: 学号 {data['student_no']} 已存在")
                continue
            stu.student_no = data["student_no"]
        if "class_id" in data and data["class_id"] is not None:
            stu.class_id = data["class_id"]
        if "original_class_id" in data:
            stu.original_class_id = data["original_class_id"]
        updated += 1
    db.commit()
    return {"updated": updated, "errors": errors}


# ---- 分班 ----

def reassign_students(db: Session, student_ids: list[int], new_class_id: int, new_combination: str = "") -> dict:
    """批量分班：将学生转移到新班级，原班级自动记录为 original_class_id"""
    target = db.get(ClassGroup, new_class_id)
    if not target:
        raise ValueError("目标班级不存在")
    combo = new_combination.strip()
    if combo and combo not in VALID_COMBINATIONS:
        raise ValueError(f"无效的选科组合: {combo}")
    reassigned = 0
    for sid in student_ids:
        stu = db.get(Student, sid)
        if stu:
            # 如果学生还没有原班级记录，保存当前班级为原班级
            if stu.original_class_id is None:
                stu.original_class_id = stu.class_id
            stu.class_id = new_class_id
            if combo:
                stu.combination = combo
            reassigned += 1
    db.commit()
    return {"reassigned": reassigned, "new_class": target.name}


# ---- 导出 ----

def export_all_students(db: Session) -> bytes:
    from app.services.import_service import export_all_students as do_export
    return do_export(db)
