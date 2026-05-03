"""
Excel 导入导出服务
"""

import io
import pandas as pd
from sqlalchemy.orm import Session

from app.models.student import Student, ClassGroup
from app.models.exam import ExamSubject
from app.models.score import Score
from app.services.score_service import upsert_score


def import_students_from_excel(db: Session, file_bytes: bytes) -> dict:
    """
    从 Excel 导入学生
    期望列：学号, 姓名, 班级, 首选科目(物理/历史), 赋分科目1, 赋分科目2
    """
    df = pd.read_excel(io.BytesIO(file_bytes))

    required_cols = {"学号", "姓名", "班级", "首选科目", "赋分科目1", "赋分科目2"}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        return {"error": f"缺少列: {', '.join(missing)}", "imported": 0}

    imported = 0
    errors = []
    for _, row in df.iterrows():
        student_no = str(row["学号"]).strip()
        name = str(row["姓名"]).strip()
        class_name = str(row["班级"]).strip()
        pref = str(row["首选科目"]).strip()
        elec1 = str(row["赋分科目1"]).strip()
        elec2 = str(row["赋分科目2"]).strip()

        # 查找或创建班级
        cls = db.query(ClassGroup).filter(ClassGroup.name == class_name).first()
        if not cls:
            # 从班级名提取年级，如 "高三(1)班" -> 12
            grade = 12  # 默认高三
            cls = ClassGroup(name=class_name, grade=grade)
            db.add(cls)
            db.flush()

        # 检查学号是否已存在
        existing = db.query(Student).filter(Student.student_no == student_no).first()
        if existing:
            # 更新
            existing.name = name
            existing.class_id = cls.id
            existing.preferred_subject = pref
            existing.elective_1 = elec1
            existing.elective_2 = elec2
        else:
            stu = Student(
                name=name,
                student_no=student_no,
                class_id=cls.id,
                preferred_subject=pref,
                elective_1=elec1,
                elective_2=elec2,
            )
            db.add(stu)
        imported += 1

    db.commit()
    return {"imported": imported, "errors": errors}


def import_scores_from_excel(db: Session, file_bytes: bytes, exam_id: int) -> dict:
    """
    从 Excel 导入成绩
    期望列：学号, 科目, 成绩
    """
    df = pd.read_excel(io.BytesIO(file_bytes))

    required_cols = {"学号", "科目", "成绩"}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        return {"error": f"缺少列: {', '.join(missing)}", "imported": 0}

    # 建立 exam_subject 映射
    exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()
    es_map = {es.subject: es for es in exam_subjects}

    imported = 0
    errors = []
    for _, row in df.iterrows():
        student_no = str(row["学号"]).strip()
        subject = str(row["科目"]).strip()
        raw_score = float(row["成绩"])

        student = db.query(Student).filter(Student.student_no == student_no).first()
        if not student:
            errors.append(f"学号 {student_no} 不存在")
            continue

        es = es_map.get(subject)
        if not es:
            errors.append(f"科目 {subject} 不在本次考试中")
            continue

        upsert_score(db, student.id, es.id, raw_score)
        imported += 1

    db.commit()
    return {"imported": imported, "errors": errors}


def export_students_template() -> bytes:
    """导出学生导入模板"""
    df = pd.DataFrame(columns=["学号", "姓名", "班级", "首选科目", "赋分科目1", "赋分科目2"])
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


def export_scores_template() -> bytes:
    """导出成绩导入模板"""
    df = pd.DataFrame(columns=["学号", "科目", "成绩"])
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


def export_exam_results(db: Session, exam_id: int) -> bytes:
    """导出某次考试的成绩汇总"""
    from app.services.score_service import get_exam_all_totals

    results = get_exam_all_totals(db, exam_id)
    if not results:
        return b""

    rows = []
    for r in results:
        row = {"排名": r["rank"], "姓名": r["student_name"], "总分": r["total"]}
        for subj, val in r["scores"].items():
            row[subj] = val
        rows.append(row)

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()
