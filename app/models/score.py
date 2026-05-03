from sqlalchemy import Column, Integer, Float, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ConversionRule(Base):
    __tablename__ = "conversion_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tier = Column(String(5), nullable=False, unique=True, comment="等级，如A1、B3")
    percentile_low = Column(Float, nullable=False, comment="百分位下限")
    percentile_high = Column(Float, nullable=False, comment="百分位上限")
    converted_low = Column(Integer, nullable=False, comment="赋分下限")
    converted_high = Column(Integer, nullable=False, comment="赋分上限")


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    exam_subject_id = Column(Integer, ForeignKey("exam_subjects.id"), nullable=False)
    raw_score = Column(Float, nullable=False)
    converted_score = Column(Float, nullable=True, comment="赋分后分数，仅赋分科目")

    student = relationship("Student", back_populates="scores")
    exam_subject = relationship("ExamSubject", back_populates="scores")

    __table_args__ = (
        UniqueConstraint("student_id", "exam_subject_id", name="uq_student_exam_subject"),
    )
