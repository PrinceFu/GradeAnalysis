from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, func
from pydantic import BaseModel
import io

from app.database import get_db
from app.models.student import Student, ClassGroup
from app.models.exam import Exam, ExamSubject
from app.models.score import Score

router = APIRouter()

VALID_COMBINATIONS = [
    "物化生", "物化政", "物化地",
    "物生政", "物生地", "物政地",
    "史政地", "史化政", "史化地",
    "史生政", "史生地", "史化生",
]

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


class ClassGroupCreate(BaseModel):
    name: str
    grade: int


class StudentCreate(BaseModel):
    name: str
    student_no: str
    class_id: int
    combination: str = ""


class StudentUpdate(BaseModel):
    name: str | None = None
    student_no: str | None = None
    class_id: int | None = None
    combination: str | None = None


# ---- 班级 ----

@router.get("/classes")
def list_classes(db: Session = Depends(get_db)):
    classes = db.query(ClassGroup).all()
    return [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes]


@router.get("/classes/with-students")
def list_classes_with_students(db: Session = Depends(get_db)):
    """返回有学生的班级（用于筛选下拉框）"""
    classes = (
        db.query(ClassGroup)
        .join(Student, Student.class_id == ClassGroup.id)
        .distinct()
        .all()
    )
    return [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes]


@router.post("/classes")
def create_class(data: ClassGroupCreate, db: Session = Depends(get_db)):
    cls = ClassGroup(name=data.name, grade=data.grade)
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return {"id": cls.id, "name": cls.name, "grade": cls.grade}


# ---- 组合信息 ----

@router.get("/combinations")
def list_combinations():
    """返回所有有效的选科组合及其包含的科目"""
    return [
        {"name": name, "subjects": subjects}
        for name, subjects in COMBINATION_SUBJECTS.items()
    ]


@router.get("/combinations/available")
def list_available_combinations(db: Session = Depends(get_db)):
    """返回数据库中学生实际使用的选科组合（用于筛选下拉框）"""
    combos = (
        db.query(Student.combination)
        .filter(Student.combination != None, Student.combination != "")
        .distinct()
        .all()
    )
    return sorted([c[0] for c in combos])


# ---- 学生 ----

SORT_FIELDS = {
    "student_no": Student.student_no,
    "name": Student.name,
    "class_name": ClassGroup.name,
    "combination": Student.combination,
}


@router.get("/export/all")
def export_all_students(db: Session = Depends(get_db)):
    """导出全部学生信息为 Excel"""
    from app.services.import_service import export_all_students as do_export
    data = do_export(db)
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
    combination: str = None,
    sort_by: str = Query(None, description="排序字段: student_no, name, class_name, combination 或科目名"),
    sort_order: str = Query("asc", description="排序方向: asc 或 desc"),
    db: Session = Depends(get_db),
):
    q = db.query(Student).join(ClassGroup)
    if class_id:
        q = q.filter(Student.class_id == class_id)
    if combination:
        q = q.filter(Student.combination == combination)

    if sort_by and sort_by in SORT_FIELDS:
        col = SORT_FIELDS[sort_by]
        q = q.order_by(desc(col) if sort_order == "desc" else asc(col))
    else:
        q = q.order_by(Student.student_no)

    students = q.all()

    # 获取最新一次考试
    latest_exam = db.query(Exam).order_by(Exam.exam_date.desc(), Exam.id.desc()).first()

    score_map = {}
    if latest_exam:
        exam_subjects = db.query(ExamSubject).filter(ExamSubject.exam_id == latest_exam.id).all()
        es_map = {es.subject: es for es in exam_subjects}
        es_ids = [es.id for es in exam_subjects]
        if es_ids:
            all_scores = db.query(Score).filter(Score.exam_subject_id.in_(es_ids)).all()
            for sc in all_scores:
                score_map[(sc.student_id, sc.exam_subject_id)] = sc

    result = []
    for s in students:
        item = {
            "id": s.id,
            "name": s.name,
            "student_no": s.student_no,
            "class_id": s.class_id,
            "class_name": s.class_group.name,
            "combination": s.combination or "",
        }
        if latest_exam:
            for es in exam_subjects:
                sc = score_map.get((s.id, es.id))
                if sc:
                    val = sc.converted_score if (es.subject in {"化学", "生物", "政治", "地理"} and sc.converted_score is not None) else sc.raw_score
                    item[es.subject] = val
                else:
                    item[es.subject] = None
        result.append(item)

    # 按科目排序（内存排序）
    SCORE_FIELDS = {"语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"}
    if sort_by in SCORE_FIELDS:
        reverse = sort_order == "desc"
        result.sort(key=lambda x: (x.get(sort_by) is None, x.get(sort_by) or 0), reverse=reverse)

    return result


@router.get("/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail="学生不存在")
    return {
        "id": s.id,
        "name": s.name,
        "student_no": s.student_no,
        "class_id": s.class_id,
        "class_name": s.class_group.name,
        "combination": s.combination or "",
    }


@router.post("/")
def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    if db.query(Student).filter(Student.student_no == data.student_no).first():
        raise HTTPException(status_code=400, detail="学号已存在")
    combo = data.combination.strip()
    if combo and combo not in VALID_COMBINATIONS:
        raise HTTPException(status_code=400, detail=f"无效的选科组合: {combo}")
    stu = Student(
        name=data.name,
        student_no=data.student_no,
        class_id=data.class_id,
        combination=combo,
    )
    db.add(stu)
    db.commit()
    db.refresh(stu)
    return {"id": stu.id, "name": stu.name, "student_no": stu.student_no}


@router.put("/{student_id}")
def update_student(student_id: int, data: StudentUpdate, db: Session = Depends(get_db)):
    stu = db.get(Student, student_id)
    if not stu:
        raise HTTPException(status_code=404, detail="学生不存在")
    if data.name is not None:
        stu.name = data.name
    if data.student_no is not None:
        existing = db.query(Student).filter(Student.student_no == data.student_no, Student.id != student_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="学号已存在")
        stu.student_no = data.student_no
    if data.class_id is not None:
        stu.class_id = data.class_id
    if data.combination is not None:
        combo = data.combination.strip()
        if combo and combo not in VALID_COMBINATIONS:
            raise HTTPException(status_code=400, detail=f"无效的选科组合: {combo}")
        stu.combination = combo
    db.commit()
    db.refresh(stu)
    return {"id": stu.id, "name": stu.name, "student_no": stu.student_no}


@router.delete("/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    stu = db.get(Student, student_id)
    if not stu:
        raise HTTPException(status_code=404, detail="学生不存在")
    db.delete(stu)
    db.commit()
    return {"ok": True}
