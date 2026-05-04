"""
成绩录入、总分计算服务
"""

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.score import Score
from app.models.exam import ExamSubject
from app.models.student import Student
from app.services.conversion_service import CONVERSION_SUBJECTS, convert_scores_for_subject

# 组合 -> 科目列表映射
COMBINATION_SUBJECTS = {
    "物化生": ["语文", "数学", "英语", "物理", "化学", "生物"],
    "物化政": ["语文", "数学", "英语", "物理", "化学", "政治"],
    "物化地": ["语文", "数学", "英语", "物理", "化学", "地理"],
    "物生政": ["语文", "数学", "英语", "物理", "生物", "政治"],
    "物生地": ["语文", "数学", "英语", "物理", "生物", "地理"],
    "物政地": ["语文", "数学", "英语", "物理", "政治", "地理"],
    "史政地": ["语文", "数学", "英语", "历史", "政治", "地理"],
    "史化政": ["语文", "数学", "英语", "历史", "化学", "政治"],
    "史化地": ["语文", "数学", "英语", "历史", "化学", "地理"],
    "史生政": ["语文", "数学", "英语", "历史", "生物", "政治"],
    "史生地": ["语文", "数学", "英语", "历史", "生物", "地理"],
    "史化生": ["语文", "数学", "英语", "历史", "化学", "生物"],
}

ALL_SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"]

# 需要赋分的科目
CONVERSION_SET = {"化学", "生物", "政治", "地理"}


def _get_subjects_for_student(student: Student) -> list[str]:
    """根据学生的组合返回需要计算的科目列表"""
    if student.combination and student.combination in COMBINATION_SUBJECTS:
        return COMBINATION_SUBJECTS[student.combination]
    return ALL_SUBJECTS


def _calc_student_total(student: Student, es_map: dict, score_getter) -> dict | None:
    """
    计算学生总分的通用逻辑
    score_getter: 接受 (student_id, exam_subject_id) 返回 Score 对象
    """
    subjects = _get_subjects_for_student(student)
    scores_detail = {}
    total = 0.0

    for subj in subjects:
        if subj not in es_map:
            continue
        score = score_getter(student.id, es_map[subj].id)
        if score:
            if subj in CONVERSION_SET and score.converted_score is not None:
                val = score.converted_score
            else:
                val = score.raw_score
            scores_detail[subj] = val
            total += val

    if not scores_detail:
        return None

    return {
        "student_id": student.id,
        "student_name": student.name,
        "scores": scores_detail,
        "total": round(total, 1),
    }


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
    return convert_scores_for_subject(db, exam_subject_id)


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
    计算某学生某次考试的总分
    根据学生的组合决定计算哪些科目
    """
    student = db.get(Student, student_id)
    if not student:
        return None

    exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()
    es_map = {es.subject: es for es in exam_subjects}

    def score_getter(sid, esid):
        return db.query(Score).filter(
            Score.student_id == sid, Score.exam_subject_id == esid
        ).first()

    return _calc_student_total(student, es_map, score_getter)


def get_exam_all_totals(db: Session, exam_id: int) -> list[dict]:
    """计算某次考试所有学生的总分（优化：单次查询）"""

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

    def score_getter(sid, esid):
        return score_map.get((sid, esid))

    results = []
    for stu in students:
        result = _calc_student_total(stu, es_map, score_getter)
        if result:
            results.append(result)

    results.sort(key=lambda x: x["total"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results
