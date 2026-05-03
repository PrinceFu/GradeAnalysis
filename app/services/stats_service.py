"""
统计分析服务：均分、优秀率、及格率、分数段分布、班级对比、纵向追踪
"""

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.student import Student, ClassGroup
from app.models.exam import Exam, ExamSubject
from app.models.score import Score
from app.services.score_service import get_exam_all_totals


def subject_stats(db: Session, exam_subject_id: int) -> dict:
    """单科统计：均分、最高分、最低分、及格率、优秀率"""
    scores = db.query(Score).filter(Score.exam_subject_id == exam_subject_id).all()
    if not scores:
        return {}

    exam_subject = db.get(ExamSubject, exam_subject_id)
    full_score = exam_subject.full_score

    # 对赋分科目用 converted_score，其他用 raw_score
    values = []
    for s in scores:
        if exam_subject.needs_conversion and s.converted_score is not None:
            values.append(s.converted_score)
        else:
            values.append(s.raw_score)

    avg = sum(values) / len(values)
    pass_line = full_score * 0.6
    excellent_line = full_score * 0.9

    return {
        "subject": exam_subject.subject,
        "count": len(values),
        "average": round(avg, 1),
        "max": max(values),
        "min": min(values),
        "pass_rate": round(sum(1 for v in values if v >= pass_line) / len(values) * 100, 1),
        "excellent_rate": round(sum(1 for v in values if v >= excellent_line) / len(values) * 100, 1),
        "full_score": full_score,
    }


def score_distribution(db: Session, exam_subject_id: int, step: int = 10) -> dict:
    """分数段分布，返回 {labels: [...], counts: [...]}"""
    scores = db.query(Score).filter(Score.exam_subject_id == exam_subject_id).all()
    if not scores:
        return {"labels": [], "counts": []}

    exam_subject = db.get(ExamSubject, exam_subject_id)
    full_score = exam_subject.full_score

    values = []
    for s in scores:
        if exam_subject.needs_conversion and s.converted_score is not None:
            values.append(s.converted_score)
        else:
            values.append(s.raw_score)

    labels = []
    counts = []
    for low in range(0, full_score, step):
        high = low + step
        label = f"{low}-{high}"
        count = sum(1 for v in values if low <= v < high)
        labels.append(label)
        counts.append(count)
    # 最后一个区间包含满分
    if full_score % step != 0:
        count = sum(1 for v in values if v == full_score)
        if counts:
            counts[-1] += count

    return {"labels": labels, "counts": counts}


def grade_overview(db: Session, exam_id: int) -> dict:
    """年级总览：各科统计 + 总分统计"""
    exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()
    subjects_stats = {}
    for es in exam_subjects:
        stats = subject_stats(db, es.id)
        if stats:
            subjects_stats[es.subject] = stats

    # 总分统计
    all_totals = get_exam_all_totals(db, exam_id)
    totals = [t["total"] for t in all_totals]
    total_stats = {}
    if totals:
        total_stats = {
            "count": len(totals),
            "average": round(sum(totals) / len(totals), 1),
            "max": max(totals),
            "min": min(totals),
        }

    return {
        "exam_id": exam_id,
        "subjects": subjects_stats,
        "total": total_stats,
    }


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


def student_trend(db: Session, student_id: int) -> list[dict]:
    """学生个人趋势：多次考试各科成绩和总分变化"""
    student = db.get(Student, student_id)
    if not student:
        return []

    exams = db.query(Exam).order_by(Exam.exam_date).all()
    trend = []

    for exam in exams:
        exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam.id).all()
        es_map = {es.subject: es for es in exam_subjects}

        exam_scores = {}
        for subj, es in es_map.items():
            score = db.query(Score).filter(
                Score.student_id == student_id,
                Score.exam_subject_id == es.id
            ).first()
            if score:
                if es.needs_conversion and score.converted_score is not None:
                    exam_scores[subj] = score.converted_score
                else:
                    exam_scores[subj] = score.raw_score

        total = sum(exam_scores.values()) if exam_scores else 0
        trend.append({
            "exam_name": exam.name,
            "exam_date": str(exam.exam_date),
            "scores": exam_scores,
            "total": round(total, 1),
        })

    return trend
