from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import io

from app.database import get_db
from app.models.exam import ExamSubject
from app.models.student import Student
from app.services.score_service import (
    upsert_score,
    batch_upsert_scores,
    trigger_conversion,
    trigger_all_conversions,
    get_student_total_score,
    get_exam_all_totals,
)
from app.services.import_service import (
    import_students_from_excel,
    import_scores_from_excel,
    export_students_template,
    export_scores_template,
    export_exam_results,
)

router = APIRouter()


class ScoreEntry(BaseModel):
    student_id: int
    raw_score: float


class BatchScoreEntry(BaseModel):
    exam_subject_id: int
    scores: list[ScoreEntry]


class SingleScoreEntry(BaseModel):
    student_id: int
    exam_subject_id: int
    raw_score: float


@router.post("/entry")
def enter_single_score(data: SingleScoreEntry, db: Session = Depends(get_db)):
    """录入单条成绩"""
    score = upsert_score(db, data.student_id, data.exam_subject_id, data.raw_score)
    db.commit()
    return {"id": score.id, "student_id": score.student_id, "raw_score": score.raw_score}


@router.post("/batch")
def enter_batch_scores(data: BatchScoreEntry, db: Session = Depends(get_db)):
    """批量录入某科目的成绩"""
    score_data = [{"student_id": s.student_id, "raw_score": s.raw_score} for s in data.scores]
    count = batch_upsert_scores(db, data.exam_subject_id, score_data)
    return {"count": count}


@router.post("/convert/{exam_subject_id}")
def do_conversion(exam_subject_id: int, db: Session = Depends(get_db)):
    """触发单科等级赋分"""
    es = db.get(ExamSubject, exam_subject_id)
    if not es:
        raise HTTPException(status_code=404, detail="考试科目不存在")
    if not es.needs_conversion:
        raise HTTPException(status_code=400, detail=f"{es.subject} 不需要等级赋分")
    results = trigger_conversion(db, exam_subject_id)
    db.commit()
    return {"subject": es.subject, "converted_count": len(results)}


@router.post("/convert-all/{exam_id}")
def do_all_conversions(exam_id: int, db: Session = Depends(get_db)):
    """触发某次考试所有赋分科目的等级赋分"""
    results = trigger_all_conversions(db, exam_id)
    return {subj: len(vals) for subj, vals in results.items()}


@router.get("/totals/{exam_id}")
def exam_totals(exam_id: int, db: Session = Depends(get_db)):
    """获取某次考试所有学生的总分排名"""
    results = get_exam_all_totals(db, exam_id)
    return results


@router.get("/totals/{exam_id}/{student_id}")
def student_total(exam_id: int, student_id: int, db: Session = Depends(get_db)):
    """获取某学生某次考试的总分详情"""
    result = get_student_total_score(db, student_id, exam_id)
    if not result:
        raise HTTPException(status_code=404, detail="数据不存在")
    return result


@router.get("/exam-subject/{exam_id}")
def list_exam_subjects(exam_id: int, db: Session = Depends(get_db)):
    """列出某次考试的所有科目"""
    subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == exam_id).all()
    return [
        {
            "id": es.id,
            "subject": es.subject,
            "full_score": es.full_score,
            "needs_conversion": es.needs_conversion,
        }
        for es in subjects
    ]


# ---- Excel 导入导出 ----

@router.post("/import/students")
async def import_students(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """从 Excel 导入学生"""
    content = await file.read()
    result = import_students_from_excel(db, content)
    return result


@router.post("/import/scores/{exam_id}")
async def import_scores(exam_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """从 Excel 导入成绩"""
    content = await file.read()
    result = import_scores_from_excel(db, content, exam_id)
    return result


@router.get("/template/students")
def download_students_template():
    """下载学生导入模板"""
    data = export_students_template()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=students_template.xlsx"},
    )


@router.get("/template/scores")
def download_scores_template():
    """下载成绩导入模板"""
    data = export_scores_template()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=scores_template.xlsx"},
    )


@router.get("/export/{exam_id}")
def export_results(exam_id: int, db: Session = Depends(get_db)):
    """导出考试成绩汇总"""
    data = export_exam_results(db, exam_id)
    if not data:
        raise HTTPException(status_code=404, detail="暂无成绩数据")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=exam_{exam_id}_results.xlsx"},
    )
