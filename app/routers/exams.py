from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from app.database import get_db
from app.models.exam import Exam, ExamSubject

router = APIRouter()

# 江苏高考所有科目
ALL_SUBJECTS = [
    ("语文", 150, False),
    ("数学", 150, False),
    ("英语", 150, False),
    ("物理", 100, False),
    ("历史", 100, False),
    ("化学", 100, True),
    ("生物", 100, True),
    ("思想政治", 100, True),
    ("地理", 100, True),
]


class ExamCreate(BaseModel):
    name: str
    exam_date: date
    exam_type: str = "模考"


@router.get("/")
def list_exams(db: Session = Depends(get_db)):
    exams = db.query(Exam).order_by(Exam.exam_date.desc()).all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "exam_date": str(e.exam_date),
            "exam_type": e.exam_type,
            "subject_count": len(e.subjects),
        }
        for e in exams
    ]


@router.get("/{exam_id}")
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    exam = db.query(Exam).get(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    return {
        "id": exam.id,
        "name": exam.name,
        "exam_date": str(exam.exam_date),
        "exam_type": exam.exam_type,
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
    exam = Exam(name=data.name, exam_date=data.exam_date, exam_type=data.exam_type)
    db.add(exam)
    db.flush()

    # 自动创建9个科目的 exam_subjects
    for subj_name, full_score, needs_conv in ALL_SUBJECTS:
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
    exam = db.query(Exam).get(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    db.delete(exam)
    db.commit()
    return {"ok": True}
