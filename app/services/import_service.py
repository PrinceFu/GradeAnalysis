"""
Excel 导入导出服务
"""

import io
from datetime import date
import pandas as pd
from sqlalchemy.orm import Session

from app.models.student import Student, ClassGroup
from app.models.exam import Exam, ExamSubject
from app.models.score import Score
from app.services.score_service import upsert_score


VALID_COMBINATIONS = [
    "物化生", "物化政", "物化地",
    "物生政", "物生地", "物政地",
    "史政地", "史化政", "史化地",
    "史生政", "史生地", "史化生",
]

# Excel 模板中的成绩列名
SCORE_COLUMNS = ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"]

# Excel 列名 -> ExamSubject.subject 的映射
COLUMN_TO_SUBJECT = {
    "语文": "语文", "数学": "数学", "英语": "英语",
    "物理": "物理", "化学": "化学", "生物": "生物",
    "政治": "政治", "历史": "历史", "地理": "地理",
}

# 创建考试时各科目的满分和是否赋分
SUBJECT_CONFIG = [
    ("语文", 150, False), ("数学", 150, False), ("英语", 150, False),
    ("物理", 100, False), ("历史", 100, False),
    ("化学", 100, True), ("生物", 100, True),
    ("政治", 100, True), ("地理", 100, True),
]


def import_students_from_excel(db: Session, file_bytes: bytes) -> dict:
    """
    从 Excel 导入学生（仅学生信息，不含成绩）
    必填列：学号, 姓名, 班级
    选填列：组合
    """
    df = pd.read_excel(io.BytesIO(file_bytes))

    # 规范化列名：去除首尾空格和不可见字符
    df.columns = [str(c).strip() for c in df.columns]

    required_cols = {"学号", "姓名", "班级"}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        return {"error": f"缺少必填列: {', '.join(missing)}。当前列: {', '.join(df.columns)}", "imported": 0}

    has_combination_col = "组合" in df.columns

    imported = 0
    errors = []
    for _, row in df.iterrows():
        student_no = str(row["学号"]).strip()
        name = str(row["姓名"]).strip()
        class_name = str(row["班级"]).strip()

        # 跳过空行
        if not student_no or student_no == "nan" or not name or name == "nan" or not class_name or class_name == "nan":
            continue

        combination = ""
        if has_combination_col:
            combination = str(row["组合"]).strip() if pd.notna(row["组合"]) else ""

        if combination and combination not in VALID_COMBINATIONS:
            errors.append(f"学号 {student_no}: 无效的组合 '{combination}'")
            continue

        # 查找或创建班级
        cls = db.query(ClassGroup).filter(ClassGroup.name == class_name).first()
        if not cls:
            grade = 12  # 默认高三
            cls = ClassGroup(name=class_name, grade=grade)
            db.add(cls)
            db.flush()

        # 检查学号是否已存在
        existing = db.query(Student).filter(Student.student_no == student_no).first()
        if existing:
            existing.name = name
            existing.class_id = cls.id
            existing.combination = combination
        else:
            student = Student(
                name=name,
                student_no=student_no,
                class_id=cls.id,
                combination=combination,
            )
            db.add(student)
        imported += 1

    db.commit()
    return {"imported": imported, "errors": errors}


def import_scores_from_excel(db: Session, file_bytes: bytes, exam_id: int) -> dict:
    """
    从 Excel 导入成绩
    期望列：学号, 班级, 组合, 姓名, 语文, 数学, 英语, 物理, 化学, 生物, 政治, 历史, 地理
    """
    df = pd.read_excel(io.BytesIO(file_bytes))

    # 规范化列名：去除首尾空格和不可见字符
    df.columns = [str(c).strip() for c in df.columns]

    required_cols = {"学号", "姓名", "班级"}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        return {"error": f"缺少必填列: {', '.join(missing)}。当前列: {', '.join(df.columns)}", "imported": 0}

    # 检查考试是否存在
    exam = db.get(Exam, exam_id)
    if not exam:
        return {"error": f"考试 ID {exam_id} 不存在", "imported": 0}

    # 建立 exam_subject 映射
    exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()
    es_map = {es.subject: es for es in exam_subjects}

    has_combination_col = "组合" in df.columns
    score_cols_in_excel = [c for c in SCORE_COLUMNS if c in df.columns]

    imported = 0
    scores_imported = 0
    errors = []
    student_details = []  # 存储每个学生的详细信息

    for _, row in df.iterrows():
        student_no = str(row["学号"]).strip()
        name = str(row["姓名"]).strip()
        class_name = str(row["班级"]).strip()

        # 跳过空行
        if not student_no or student_no == "nan" or not name or name == "nan" or not class_name or class_name == "nan":
            continue

        combination = ""
        if has_combination_col:
            combination = str(row["组合"]).strip() if pd.notna(row["组合"]) else ""

        if combination and combination not in VALID_COMBINATIONS:
            errors.append(f"学号 {student_no}: 无效的组合 '{combination}'")
            continue

        # 查找或创建班级
        cls = db.query(ClassGroup).filter(ClassGroup.name == class_name).first()
        if not cls:
            grade = 12  # 默认高三
            cls = ClassGroup(name=class_name, grade=grade)
            db.add(cls)
            db.flush()

        # 检查学号是否已存在
        student = db.query(Student).filter(Student.student_no == student_no).first()
        if student:
            # 更新学生信息
            student.name = name
            student.class_id = cls.id
            if combination:
                student.combination = combination
        else:
            # 创建新学生
            student = Student(
                name=name,
                student_no=student_no,
                class_id=cls.id,
                combination=combination,
            )
            db.add(student)
            db.flush()
        imported += 1

        # 收集该学生的成绩信息
        student_scores = {}
        for col_name in score_cols_in_excel:
            val = row[col_name]
            if pd.isna(val):
                continue
            try:
                raw_score = float(val)
            except (ValueError, TypeError):
                errors.append(f"学号 {student_no} {col_name}: 无效成绩值 '{val}'")
                continue
            subj_name = COLUMN_TO_SUBJECT.get(col_name)
            es = es_map.get(subj_name)
            if not es:
                continue
            upsert_score(db, student.id, es.id, raw_score)
            scores_imported += 1
            student_scores[col_name] = raw_score

        # 记录学生详细信息
        student_details.append({
            "student_no": student_no,
            "name": name,
            "class_name": class_name,
            "combination": combination,
            "scores": student_scores,
        })

    db.commit()
    return {
        "imported": imported,
        "scores_imported": scores_imported,
        "errors": errors,
        "student_details": student_details,
    }


def export_students_template() -> bytes:
    """导出学生导入模板"""
    df = pd.DataFrame(columns=["学号", "姓名", "班级", "组合"])
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


def export_scores_template() -> bytes:
    """导出成绩导入模板"""
    df = pd.DataFrame(columns=["学号", "班级", "组合", "姓名", "语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"])
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


def export_all_students(db: Session) -> bytes:
    """导出全部学生信息（含最新考试成绩）"""
    from app.models.exam import Exam, ExamSubject
    from app.models.score import Score
    from app.services.conversion_service import CONVERSION_SUBJECTS

    students = db.query(Student).join(ClassGroup).order_by(Student.student_no).all()
    if not students:
        return b""

    # 获取最新考试
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

    es_map = {es.subject: es for es in exam_subjects}

    rows = []
    for s in students:
        row = {
            "学号": s.student_no,
            "姓名": s.name,
            "班级": s.class_group.name,
            "组合": s.combination or "",
        }
        for subj in ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"]:
            if subj in es_map:
                sc = score_map.get((s.id, es_map[subj].id))
                if sc:
                    val = sc.converted_score if (subj in CONVERSION_SUBJECTS and sc.converted_score is not None) else sc.raw_score
                    row[subj] = val
                else:
                    row[subj] = ""
            else:
                row[subj] = ""
        rows.append(row)

    df = pd.DataFrame(rows)
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
