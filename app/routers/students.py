from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import io

from app.database import get_db
from app.services import student_service

router = APIRouter()


# ---- Pydantic Models ----

class StudentCreate(BaseModel):
    name: str
    student_no: str
    class_id: int
    combination: str = ""
    id_card: str = ""
    gender: str = ""


class StudentUpdate(BaseModel):
    name: str | None = None
    student_no: str | None = None
    class_id: int | None = None
    combination: str | None = None
    id_card: str | None = None
    gender: str | None = None


class BatchStudentIds(BaseModel):
    student_ids: list[int]


class BatchUpdateClass(BaseModel):
    student_ids: list[int]
    class_id: int


class BatchUpdateCombination(BaseModel):
    student_ids: list[int]
    combination: str


class BatchReassign(BaseModel):
    student_ids: list[int]
    new_class_id: int
    new_combination: str = ""


class BatchUpdateStudents(BaseModel):
    student_ids: list[int]
    student_no: str | None = None
    class_id: int | None = None
    original_class_id: int | None = None


# ---- 班级 ----

@router.get("/classes")
def list_classes(db: Session = Depends(get_db)):
    return student_service.list_classes(db)


@router.get("/classes/with-students")
def list_classes_with_students(db: Session = Depends(get_db)):
    return student_service.list_classes_with_students(db)


# ---- 组合信息 ----

@router.get("/combinations")
def list_combinations():
    return student_service.list_combinations()


@router.get("/combinations/available")
def list_available_combinations(db: Session = Depends(get_db)):
    return student_service.list_available_combinations(db)


@router.get("/enrollment-years/available")
def list_available_enrollment_years(db: Session = Depends(get_db)):
    return student_service.list_available_enrollment_years(db)


@router.get("/grade-levels")
def list_grade_levels(db: Session = Depends(get_db)):
    """根据学生入学年份返回可用的年级列表，用于考试对象选择"""
    from app.models.student import Student

    years = (
        db.query(Student.enrollment_year)
        .filter(Student.enrollment_year.isnot(None))
        .distinct()
        .all()
    )
    result = []
    for (year,) in years:
        result.append({"value": str(year), "label": f"{year}级", "enrollment_year": year})
    # 按入学年份从高到低排序
    result.sort(key=lambda x: x["enrollment_year"], reverse=True)
    return result


# ---- 学生 ----

@router.get("/export/all")
def export_all_students(db: Session = Depends(get_db)):
    data = student_service.export_all_students(db)
    if not data:
        raise HTTPException(status_code=404, detail="暂无学生数据")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=all_students.xlsx"},
    )


@router.get("/")
def list_students(
    class_id: int = None,
    original_class_id: int = None,
    enrollment_year: int = None,
    combination: str = None,
    search: str = None,
    sort_by: str = Query(None, description="排序字段: student_no, name, class_name, combination, enrollment_year 或科目名"),
    sort_order: str = Query("asc", description="排序方向: asc 或 desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(300, ge=5, le=1500, description="每页数量"),
    db: Session = Depends(get_db),
):
    return student_service.list_students(
        db, class_id=class_id, original_class_id=original_class_id,
        enrollment_year=enrollment_year, combination=combination, search=search,
        sort_by=sort_by, sort_order=sort_order, page=page, page_size=page_size,
    )


@router.get("/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    try:
        return student_service.get_student(db, student_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="学生不存在")


@router.get("/{student_id}/score-count")
def student_score_count(student_id: int, db: Session = Depends(get_db)):
    return {"score_count": student_service.get_student_score_count(db, student_id)}


@router.post("/")
def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    try:
        return student_service.create_student(db, data.name, data.student_no, data.class_id, data.combination, data.id_card, data.gender)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{student_id}")
def update_student(student_id: int, data: StudentUpdate, db: Session = Depends(get_db)):
    try:
        return student_service.update_student(db, student_id, data.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    try:
        return student_service.delete_student(db, student_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="学生不存在")


# ---- 批量操作 ----

@router.post("/batch-delete")
def batch_delete(data: BatchStudentIds, db: Session = Depends(get_db)):
    return student_service.batch_delete_students(db, data.student_ids)


@router.post("/batch-update-class")
def batch_update_class(data: BatchUpdateClass, db: Session = Depends(get_db)):
    try:
        return student_service.batch_update_class(db, data.student_ids, data.class_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch-update-combination")
def batch_update_combination(data: BatchUpdateCombination, db: Session = Depends(get_db)):
    try:
        return student_service.batch_update_combination(db, data.student_ids, data.combination)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch-reassign")
def batch_reassign(data: BatchReassign, db: Session = Depends(get_db)):
    """批量分班：转移学生到新班级，自动记录原班级"""
    try:
        return student_service.reassign_students(db, data.student_ids, data.new_class_id, data.new_combination)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch-update-students")
def batch_update_students(data: BatchUpdateStudents, db: Session = Depends(get_db)):
    """批量更新学生信息（学号、班级、原班级），不影响成绩记录"""
    update_data = {}
    if data.student_no is not None:
        update_data["student_no"] = data.student_no
    if data.class_id is not None:
        update_data["class_id"] = data.class_id
    if data.original_class_id is not None:
        update_data["original_class_id"] = data.original_class_id
    return student_service.batch_update_students(db, data.student_ids, update_data)
