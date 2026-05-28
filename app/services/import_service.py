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
from app.constants import VALID_COMBINATIONS, SCORE_COLUMNS, COLUMN_TO_SUBJECT, SUBJECT_CONFIG, CONVERSION_SUBJECTS


def _normalize_student_no(val) -> str:
    """将学号标准化为纯数字字符串，处理浮点数和科学计数法"""
    if pd.isna(val):
        return ""
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return str(val).strip()
    return str(val).strip()


def _parse_student_excel(file_bytes: bytes) -> tuple:
    """解析学生 Excel 文件，返回 (DataFrame, error_dict_or_None, flags_dict)"""
    df = pd.read_excel(io.BytesIO(file_bytes))
    df.columns = [str(c).strip() for c in df.columns]

    required_cols = {"学号", "姓名", "班级"}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        return None, {"error": f"缺少必填列: {', '.join(missing)}。当前列: {', '.join(df.columns)}", "imported": 0}, {}

    flags = {
        "has_combination": "组合" in df.columns,
        "has_id_card": "身份证号" in df.columns,
        "has_enrollment_year": "入学年份" in df.columns,
        "has_original_class": "原班级" in df.columns,
        "has_gender": "性别" in df.columns,
    }
    return df, None, flags


def _iter_student_rows(df, flags):
    """遍历 DataFrame 中的有效学生行，yield (student_no, name, class_name, combination, id_card, enrollment_year, original_class, gender)"""
    for _, row in df.iterrows():
        student_no = _normalize_student_no(row["学号"])
        name = str(row["姓名"]).strip()
        class_name = str(row["班级"]).strip()
        if not student_no or student_no == "nan" or not name or name == "nan" or not class_name or class_name == "nan":
            continue
        combination = ""
        if flags.get("has_combination"):
            combination = str(row["组合"]).strip() if pd.notna(row["组合"]) else ""
        id_card = ""
        if flags.get("has_id_card"):
            id_card = str(row["身份证号"]).strip() if pd.notna(row.get("身份证号")) else ""
            if id_card == "nan":
                id_card = ""
        enrollment_year = None
        if flags.get("has_enrollment_year"):
            val = row.get("入学年份")
            if pd.notna(val):
                try:
                    enrollment_year = int(float(val))
                except (ValueError, TypeError):
                    pass
        original_class = ""
        if flags.get("has_original_class"):
            original_class = str(row.get("原班级", "")).strip()
            if original_class == "nan":
                original_class = ""
        gender = ""
        if flags.get("has_gender"):
            gender = str(row.get("性别", "")).strip()
            if gender == "nan":
                gender = ""
        yield student_no, name, class_name, combination, id_card, enrollment_year, original_class, gender


def preview_students_import(db: Session, file_bytes: bytes, grade: int = 12) -> dict:
    """预览导入结果，不写入数据库"""
    df, err, flags = _parse_student_excel(file_bytes)
    if err:
        return err

    new_students = []
    existing_students = []
    errors = []
    classes_to_create = set()
    all_class_names = set()

    for student_no, name, class_name, combination, id_card, enrollment_year, original_class, gender in _iter_student_rows(df, flags):
        if combination and combination not in VALID_COMBINATIONS:
            errors.append(f"学号 {student_no}: 无效的组合 '{combination}'")
            continue

        cls = db.query(ClassGroup).filter(ClassGroup.name == class_name).first()
        if not cls:
            classes_to_create.add(class_name)
        all_class_names.add(class_name)

        existing = db.query(Student).filter(Student.student_no == student_no).first()
        info = {"student_no": student_no, "name": name, "class_name": class_name, "combination": combination}
        if id_card:
            info["id_card"] = id_card
        if enrollment_year:
            info["enrollment_year"] = enrollment_year
        if original_class:
            info["original_class"] = original_class
        if gender:
            info["gender"] = gender
        if existing:
            existing_students.append(info)
        else:
            new_students.append(info)

    return {
        "total_rows": len(new_students) + len(existing_students) + len(errors),
        "new_students": new_students,
        "existing_students": existing_students,
        "errors": errors,
        "classes_to_create": sorted(classes_to_create),
    }


def import_students_from_excel(db: Session, file_bytes: bytes, grade: int = 12) -> dict:
    """
    从 Excel 导入学生（仅学生信息，不含成绩）
    必填列：学号, 姓名, 班级
    选填列：组合, 身份证号, 入学年份, 原班级, 性别
    """
    df, err, flags = _parse_student_excel(file_bytes)
    if err:
        return err

    imported = 0
    errors = []
    for student_no, name, class_name, combination, id_card, enrollment_year, original_class, gender in _iter_student_rows(df, flags):
        if combination and combination not in VALID_COMBINATIONS:
            errors.append(f"学号 {student_no}: 无效的组合 '{combination}'")
            continue

        # 查找或创建现班级
        cls = db.query(ClassGroup).filter(ClassGroup.name == class_name).first()
        if not cls:
            cls = ClassGroup(name=class_name, grade=grade)
            db.add(cls)
            db.flush()

        # 查找原班级（如果指定）
        original_class_id = None
        if original_class:
            orig_cls = db.query(ClassGroup).filter(ClassGroup.name == original_class).first()
            if not orig_cls:
                orig_cls = ClassGroup(name=original_class, grade=grade)
                db.add(orig_cls)
                db.flush()
            original_class_id = orig_cls.id

        # 检查学号是否已存在
        existing = db.query(Student).filter(Student.student_no == student_no).first()
        if existing:
            existing.name = name
            existing.class_id = cls.id
            existing.combination = combination
            if id_card:
                existing.id_card = id_card
            if enrollment_year:
                existing.enrollment_year = enrollment_year
            if original_class_id:
                existing.original_class_id = original_class_id
            if gender:
                existing.gender = gender
        else:
            student = Student(
                name=name,
                student_no=student_no,
                class_id=cls.id,
                combination=combination,
                id_card=id_card if id_card else None,
                enrollment_year=enrollment_year,
                original_class_id=original_class_id,
                gender=gender,
            )
            db.add(student)
        imported += 1

    db.commit()
    return {"imported": imported, "errors": errors}


def import_scores_from_excel(db: Session, file_bytes: bytes, exam_id: int) -> dict:
    """
    从 Excel 导入成绩。
    支持灵活表头匹配：按列名匹配，不要求列顺序与模板一致。
    必填列：学号、姓名。班级列为可选（学生在学生管理中已绑定班级）。
    """
    df = pd.read_excel(io.BytesIO(file_bytes))

    # 规范化列名：去除首尾空格和不可见字符
    df.columns = [str(c).strip() for c in df.columns]

    # 必填列（班级不再必需）
    required_cols = {"学号", "姓名"}
    if not required_cols.issubset(set(df.columns)):
        missing = required_cols - set(df.columns)
        return {"error": f"缺少必填列: {', '.join(missing)}。当前列: {', '.join(df.columns)}", "imported": 0, "scores_imported": 0, "errors": [], "student_details": []}

    # 班级列为可选，支持"现班级"和"班级"两种列名
    class_col = None
    if "现班级" in df.columns:
        class_col = "现班级"
    elif "班级" in df.columns:
        class_col = "班级"

    # 检查考试是否存在
    exam = db.get(Exam, exam_id)
    if not exam:
        return {"error": f"考试 ID {exam_id} 不存在", "imported": 0, "scores_imported": 0, "errors": [], "student_details": []}

    # 建立 exam_subject 映射
    exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()
    es_map = {es.subject: es for es in exam_subjects}

    score_cols_in_excel = [c for c in SCORE_COLUMNS if c in df.columns]

    imported = 0
    scores_imported = 0
    errors = []
    student_details = []

    for _, row in df.iterrows():
        student_no = _normalize_student_no(row["学号"])
        name = str(row["姓名"]).strip()

        # 跳过空行
        if not student_no or student_no == "nan" or not name or name == "nan":
            continue

        # 按学号查找学生（不自动创建）
        student = db.query(Student).filter(Student.student_no == student_no).first()
        if not student:
            errors.append(f"学号 {student_no}: 学生不存在，请先在学生管理中导入该学生")
            continue

        # 更新姓名
        if name != student.name:
            student.name = name

        # 如果包含班级列，可选择更新学生班级
        if class_col:
            class_name = str(row[class_col]).strip()
            if class_name and class_name != "nan":
                cls = db.query(ClassGroup).filter(ClassGroup.name == class_name).first()
                if not cls:
                    cls = ClassGroup(name=class_name, grade=12)
                    db.add(cls)
                    db.flush()
                if student.class_id != cls.id:
                    student.class_id = cls.id

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
            "name": student.name,
            "class_name": student.class_group.name if student.class_group else "",
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
    df = pd.DataFrame(columns=["学号", "姓名", "班级", "原班级", "性别", "组合", "身份证号", "入学年份"])
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


def export_scores_template() -> bytes:
    """导出成绩导入模板（班级信息已在学生管理中维护，无需重复填写）"""
    df = pd.DataFrame(columns=["学号", "姓名", "语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"])
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


def export_all_students(db: Session) -> bytes:
    """导出全部学生信息（含最新考试成绩）"""
    from app.models.exam import Exam, ExamSubject
    from app.models.score import Score

    students = db.query(Student).join(ClassGroup, Student.class_id == ClassGroup.id).order_by(Student.student_no).all()
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
            "原班级": s.original_class_group.name if s.original_class_group else "",
            "性别": s.gender or "",
            "组合": s.combination or "",
            "身份证号": s.id_card or "",
            "入学年份": s.enrollment_year or "",
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
