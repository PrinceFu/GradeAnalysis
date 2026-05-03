"""
成绩录入、总分计算服务
"""

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.score import Score
from app.models.exam import ExamSubject
from app.models.student import Student
from app.services.conversion_service import CONVERSION_SUBJECTS, convert_scores_for_subject_v2


def upsert_score(db: Session, student_id: int, exam_subject_id: int, raw_score: float) -> Score:
    """录入或更新某学生某科目的成绩"""
    score = (
        db.query(Score)
        .filter(Score.student_id == student_id, Score.exam_subject_id == exam_subject_id)
        .first()
    )
    if score:
        score.raw_score = raw_score
        score.converted_score = None  # 需要重新赋分
    else:
        score = Score(student_id=student_id, exam_subject_id=exam_subject_id, raw_score=raw_score)
        db.add(score)
    db.flush()
    return score


def batch_upsert_scores(db: Session, exam_subject_id: int, score_data: list[dict]) -> int:
    """
    批量录入成绩
    score_data: [{"student_id": int, "raw_score": float}, ...]
    返回录入/更新的数量
    """
    count = 0
    for item in score_data:
        upsert_score(db, item["student_id"], exam_subject_id, item["raw_score"])
        count += 1
    db.commit()
    return count


def trigger_conversion(db: Session, exam_subject_id: int) -> list[dict]:
    """触发某科目的等级赋分计算"""
    return convert_scores_for_subject_v2(db, exam_subject_id)


def trigger_all_conversions(db: Session, exam_id: int) -> dict:
    """触发某次考试所有赋分科目的等级赋分"""
    exam_subjects = (
        db.query(ExamSubject)
        .filter(ExamSubject.exam_id == exam_id, ExamSubject.needs_conversion == True)
        .all()
    )
    results = {}
    for es in exam_subjects:
        results[es.subject] = trigger_conversion(db, es.id)
    db.commit()
    return results


def get_student_total_score(db: Session, student_id: int, exam_id: int) -> dict | None:
    """
    计算某学生某次考试的总分（3+1+2）
    返回 {"student_id", "scores": {subject: score}, "total"}
    """
    student = db.query(Student).get(student_id)
    if not student:
        return None

    exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()
    es_map = {es.subject: es for es in exam_subjects}

    scores_detail = {}
    total = 0.0

    # 3 科必考：语文、数学、英语（原始分）
    for subj in ["语文", "数学", "英语"]:
        if subj in es_map:
            score = db.query(Score).filter(
                Score.student_id == student_id,
                Score.exam_subject_id == es_map[subj].id
            ).first()
            if score:
                scores_detail[subj] = score.raw_score
                total += score.raw_score

    # "1" 选科：物理或历史（原始分）
    pref = student.preferred_subject
    if pref in es_map:
        score = db.query(Score).filter(
            Score.student_id == student_id,
            Score.exam_subject_id == es_map[pref].id
        ).first()
        if score:
            scores_detail[pref] = score.raw_score
            total += score.raw_score

    # "2" 赋分科目（赋分后分数）
    for elec in [student.elective_1, student.elective_2]:
        if elec in es_map:
            score = db.query(Score).filter(
                Score.student_id == student_id,
                Score.exam_subject_id == es_map[elec].id
            ).first()
            if score:
                val = score.converted_score if score.converted_score is not None else score.raw_score
                scores_detail[elec] = val
                total += val

    return {
        "student_id": student_id,
        "student_name": student.name,
        "scores": scores_detail,
        "total": round(total, 1),
    }


def get_exam_all_totals(db: Session, exam_id: int) -> list[dict]:
    """计算某次考试所有学生的总分"""
    students = db.query(Student).all()
    results = []
    for stu in students:
        result = get_student_total_score(db, stu.id, exam_id)
        if result:
            results.append(result)
    # 按总分降序
    results.sort(key=lambda x: x["total"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results
