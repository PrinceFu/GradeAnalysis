from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.stats_service import (
    subject_stats,
    score_distribution,
    grade_overview,
    class_comparison,
    student_trend,
)

router = APIRouter()


@router.get("/subject/{exam_subject_id}")
def get_subject_stats(exam_subject_id: int, db: Session = Depends(get_db)):
    """单科统计"""
    return subject_stats(db, exam_subject_id)


@router.get("/distribution/{exam_subject_id}")
def get_distribution(exam_subject_id: int, step: int = Query(10, ge=5, le=50), db: Session = Depends(get_db)):
    """分数段分布"""
    return score_distribution(db, exam_subject_id, step)


@router.get("/grade/{exam_id}")
def get_grade_overview(exam_id: int, db: Session = Depends(get_db)):
    """年级总览"""
    return grade_overview(db, exam_id)


@router.get("/class-comparison/{exam_id}")
def get_class_comparison(exam_id: int, db: Session = Depends(get_db)):
    """班级对比"""
    return class_comparison(db, exam_id)


@router.get("/student-trend/{student_id}")
def get_student_trend(student_id: int, db: Session = Depends(get_db)):
    """学生纵向趋势"""
    return student_trend(db, student_id)
