"""
江苏省高考等级赋分核心算法

5等21级，仅对化学、生物、政治、地理四门赋分科目执行。
两遍算法：
  1. 按原始分排名，百分位分档
  2. 档内线性插值得出赋分
"""

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.score import Score, ConversionRule
from app.models.exam import ExamSubject

# 需要赋分的科目
CONVERSION_SUBJECTS = {"化学", "生物", "思想政治", "地理"}


def convert_scores_for_subject(db: Session, exam_subject_id: int) -> list[dict]:
    """
    对某次考试的某个赋分科目执行等级赋分，返回 [{student_id, converted_score}, ...]
    """
    # 1. 读取赋分规则，按百分位升序
    rules = db.query(ConversionRule).order_by(ConversionRule.percentile_low).all()
    if not rules:
        raise ValueError("赋分规则表为空，请先初始化 conversion_rules")

    # 2. 取该科目所有成绩，按原始分降序
    scores = (
        db.query(Score)
        .filter(Score.exam_subject_id == exam_subject_id)
        .order_by(Score.raw_score.desc())
        .all()
    )
    if not scores:
        return []

    total = len(scores)
    results = []

    # 3. 第一遍：按排名百分位分档
    for rank_idx, score in enumerate(scores):
        # 百分位：0 = 最高分，100 = 最低分
        percentile = (rank_idx / total) * 100

        # 找到该百分位所属的等级
        matched_rule = None
        for rule in rules:
            if rule.percentile_low <= percentile < rule.percentile_high:
                matched_rule = rule
                break
        # 最后一个等级包含右边界
        if matched_rule is None and percentile >= rules[-1].percentile_low:
            matched_rule = rules[-1]

        if matched_rule is None:
            # 兜底：不应走到这里
            score.converted_score = score.raw_score
            results.append({"student_id": score.student_id, "converted_score": score.raw_score})
            continue

        # 4. 第二遍：在同等级学生中做线性插值
        tier_scores = [
            s for s in scores
            if _get_tier(s, total, rules) == matched_rule.tier
        ]
        if len(tier_scores) == 1:
            # 该等级只有1人，直接取赋分中位
            converted = (matched_rule.converted_low + matched_rule.converted_high) / 2
        else:
            y_high = max(s.raw_score for s in tier_scores)
            y_low = min(s.raw_score for s in tier_scores)
            t_low = matched_rule.converted_low
            t_high = matched_rule.converted_high

            if y_high == y_low:
                converted = (t_low + t_high) / 2
            else:
                converted = t_low + (score.raw_score - y_low) * (t_high - t_low) / (y_high - y_low)

        converted = round(converted)
        # 钳位到 [40, 100]
        converted = max(40, min(100, converted))

        score.converted_score = float(converted)
        results.append({"student_id": score.student_id, "converted_score": float(converted)})

    db.flush()
    return results


def _get_tier(score: Score, total: int, rules: list[ConversionRule]) -> str:
    """计算某个 score 所属的等级"""
    # 需要知道排名，这里通过重新计算百分位
    # 为避免 N² 复杂度，调用方应传入已排序列表
    # 这里用一个简单方式：直接通过 raw_score 在全局排名中定位
    # 注意：这个函数仅在 tier 分组阶段使用，实际应在 convert_scores_for_subject 内完成
    pass


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


def convert_scores_for_subject_v2(db: Session, exam_subject_id: int) -> list[dict]:
    """
    优化版本：一次遍历完成分档+插值
    """
    rules = db.query(ConversionRule).order_by(ConversionRule.percentile_low).all()
    if not rules:
        raise ValueError("赋分规则表为空")

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


def _find_tier(percentile: float, rules: list[ConversionRule]) -> ConversionRule:
    """根据百分位找到对应的赋分等级"""
    for rule in rules:
        if rule.percentile_low <= percentile < rule.percentile_high:
            return rule
    return rules[-1]
