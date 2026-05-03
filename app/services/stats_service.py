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
    """班级对比：每个班级各科均分和总分均分"""
    classes = db.query(ClassGroup).all()
    exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()

    result = []
    for cls in classes:
        student_ids = [s.id for s in db.query(Student).filter(Student.class_id == cls.id).all()]
        if not student_ids:
            continue

        cls_data = {"class_name": cls.name, "student_count": len(student_ids), "subjects": {}}

        for es in exam_subjects:
            scores = (
                db.query(Score)
                .filter(Score.exam_subject_id == es.id, Score.student_id.in_(student_ids))
                .all()
            )
            if not scores:
                continue

            values = []
            for s in scores:
                if es.needs_conversion and s.converted_score is not None:
                    values.append(s.converted_score)
                else:
                    values.append(s.raw_score)

            cls_data["subjects"][es.subject] = round(sum(values) / len(values), 1) if values else 0

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
