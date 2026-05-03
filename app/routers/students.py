from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.student import Student, ClassGroup

router = APIRouter()


class ClassGroupCreate(BaseModel):
    name: str
    grade: int


class StudentCreate(BaseModel):
    name: str
    student_no: str
    class_id: int
    preferred_subject: str
    elective_1: str
    elective_2: str


# ---- 班级 ----

@router.get("/classes")
def list_classes(db: Session = Depends(get_db)):
    classes = db.query(ClassGroup).all()
    return [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes]


@router.post("/classes")
def create_class(data: ClassGroupCreate, db: Session = Depends(get_db)):
    cls = ClassGroup(name=data.name, grade=data.grade)
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return {"id": cls.id, "name": cls.name, "grade": cls.grade}


# ---- 学生 ----

@router.get("/")
def list_students(class_id: int = None, db: Session = Depends(get_db)):
    q = db.query(Student)
    if class_id:
        q = q.filter(Student.class_id == class_id)
    students = q.all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "student_no": s.student_no,
            "class_id": s.class_id,
            "class_name": s.class_group.name,
            "preferred_subject": s.preferred_subject,
            "elective_1": s.elective_1,
            "elective_2": s.elective_2,
        }
        for s in students
    ]


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
        "preferred_subject": s.preferred_subject,
        "elective_1": s.elective_1,
        "elective_2": s.elective_2,
    }


@router.post("/")
def create_student(data: StudentCreate, db: Session = Depends(get_db)):
    if db.query(Student).filter(Student.student_no == data.student_no).first():
        raise HTTPException(status_code=400, detail="学号已存在")
    stu = Student(**data.model_dump())
    db.add(stu)
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
