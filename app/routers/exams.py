from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import date

from app.database import get_db
from app.models.exam import Exam, ExamSubject
from app.models.student import Student, ClassGroup
from app.models.score import Score
from app.constants import SUBJECT_CONFIG

router = APIRouter()


class ExamCreate(BaseModel):
    name: str
    exam_date: date
    exam_type: str = "模考"
    post_split: bool = False
    exam_target: str = "全部"


@router.get("/")
def list_exams(
    exam_type: str = Query(None),
    exam_target: str = Query(None),
    keyword: str = Query(None),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
):
    q = db.query(Exam)

    if exam_type:
        q = q.filter(Exam.exam_type == exam_type)
    if exam_target:
        q = q.filter(Exam.exam_target == exam_target)
    if keyword:
        q = q.filter(Exam.name.contains(keyword))

    if sort_order == "asc":
        q = q.order_by(Exam.exam_date.asc())
    else:
        q = q.order_by(Exam.exam_date.desc())

    exams = q.all()
    result = []
    for e in exams:
        # 检查该考试是否有成绩数据
        es_ids = [es.id for es in e.subjects]
        has_scores = False
        if es_ids:
            score_count = db.query(func.count(Score.id)).filter(Score.exam_subject_id.in_(es_ids)).scalar()
            has_scores = score_count > 0
        result.append({
            "id": e.id,
            "name": e.name,
            "exam_date": str(e.exam_date),
            "exam_type": e.exam_type,
            "post_split": e.post_split,
            "exam_target": e.exam_target or "全部",
            "subject_count": len(e.subjects),
            "has_scores": has_scores,
            "is_calculated": bool(e.is_calculated),
        })
    return result


@router.get("/{exam_id}")
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    return {
        "id": exam.id,
        "name": exam.name,
        "exam_date": str(exam.exam_date),
        "exam_type": exam.exam_type,
        "post_split": exam.post_split,
        "exam_target": exam.exam_target or "全部",
        "subjects": [
            {
                "id": es.id,
                "subject": es.subject,
                "full_score": es.full_score,
                "needs_conversion": es.needs_conversion,
            }
            for es in exam.subjects
        ],
    }


@router.post("/")
def create_exam(data: ExamCreate, db: Session = Depends(get_db)):
    exam = Exam(name=data.name, exam_date=data.exam_date, exam_type=data.exam_type, post_split=data.post_split, exam_target=data.exam_target)
    db.add(exam)
    db.flush()

    # 自动创建9个科目的 exam_subjects
    for subj_name, full_score, needs_conv in SUBJECT_CONFIG:
        es = ExamSubject(
            exam_id=exam.id,
            subject=subj_name,
            full_score=full_score,
            needs_conversion=needs_conv,
        )
        db.add(es)

    db.commit()
    db.refresh(exam)
    return {"id": exam.id, "name": exam.name}


@router.delete("/{exam_id}")
def delete_exam(exam_id: int, db: Session = Depends(get_db)):
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    db.delete(exam)
    db.commit()
    return {"ok": True}


class CalcRequest(BaseModel):
    template_id: int | None = None


@router.post("/{exam_id}/calculate")
def calculate_exam(exam_id: int, data: CalcRequest | None = None, db: Session = Depends(get_db)):
    """执行成绩计算，标记考试为已计算。传入 template_id 则同时计算赋分"""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    from app.services.grade_calc_service import calculate_grades
    template_id = data.template_id if data else None
    use_conversion = template_id is not None
    try:
        result = calculate_grades(db, exam_id, use_conversion=use_conversion, template_id=template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 标记为已计算
    exam.is_calculated = True
    db.commit()
    return result


@router.get("/{exam_id}/calc-result")
def get_calc_result(exam_id: int, template_id: int | None = None, db: Session = Depends(get_db)):
    """获取成绩计算结果，传入 template_id 则返回赋分结果；未传则自动使用默认赋分模板"""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    from app.services.grade_calc_service import calculate_grades
    from app.models.score import ConversionTemplate
    # 未指定 template_id 时，自动查找默认赋分模板
    if template_id is None:
        default_tpl = db.query(ConversionTemplate).first()
        if default_tpl:
            template_id = default_tpl.id
    use_conversion = template_id is not None
    try:
        result = calculate_grades(db, exam_id, use_conversion=use_conversion, template_id=template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/{exam_id}/reset-calculation")
def reset_calculation(exam_id: int, db: Session = Depends(get_db)):
    """重置计算状态（成绩变更后需要重新计算）"""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    exam.is_calculated = False
    db.commit()
    return {"ok": True}


@router.post("/clear-all-data")
def clear_all_data(db: Session = Depends(get_db)):
    """清除所有学生、考试、成绩数据（保留管理员账户和赋分规则）"""
    try:
        # 按照外键依赖顺序删除
        db.query(Score).delete()
        db.query(ExamSubject).delete()
        db.query(Exam).delete()
        db.query(Student).delete()
        db.query(ClassGroup).delete()
        db.commit()
        return {"ok": True, "message": "所有数据已清除"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"清除数据失败: {str(e)}")
