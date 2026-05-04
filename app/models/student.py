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
    combination = Column(String(20), nullable=True, default="", comment="选科组合，如物化生、史政地；为空则计算全部科目")

    class_group = relationship("ClassGroup", back_populates="students")
    scores = relationship("Score", back_populates="student")
