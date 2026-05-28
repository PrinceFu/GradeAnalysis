from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ClassGroup(Base):
    __tablename__ = "class_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    grade = Column(Integer, nullable=False, comment="年级，如12表示高三")

    students = relationship("Student", back_populates="class_group", foreign_keys="Student.class_id")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    student_no = Column(String(20), unique=True, nullable=False)
    class_id = Column(Integer, ForeignKey("class_groups.id"), nullable=False)
    original_class_id = Column(Integer, ForeignKey("class_groups.id"), nullable=True, comment="分班前的原班级")
    combination = Column(String(20), nullable=True, default="", comment="选科组合，如物化生、史政地；为空则计算全部科目")
    id_card = Column(String(18), nullable=True, unique=True, comment="身份证号")
    enrollment_year = Column(Integer, nullable=True, comment="入学年份，如2023")
    gender = Column(String(2), nullable=True, default="", comment="性别：男/女")

    class_group = relationship("ClassGroup", back_populates="students", foreign_keys=[class_id])
    original_class_group = relationship("ClassGroup", foreign_keys=[original_class_id])
    scores = relationship("Score", back_populates="student", cascade="all, delete-orphan")
