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
from app.constants import CONVERSION_SUBJECTS


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
