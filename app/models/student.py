from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ClassGroup(Base):
    __tablename__ = "class_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    grade = Column(Integer, nullable=False, comment="年级，如12表示高三")

    students = relationship("Student", back_populates="class_group")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    student_no = Column(String(20), unique=True, nullable=False)
    class_id = Column(Integer, ForeignKey("class_groups.id"), nullable=False)
    preferred_subject = Column(String(10), nullable=False, comment="物理或历史")
    elective_1 = Column(String(10), nullable=False, comment="赋分科目1")
    elective_2 = Column(String(10), nullable=False, comment="赋分科目2")

    class_group = relationship("ClassGroup", back_populates="students")
    scores = relationship("Score", back_populates="student")
