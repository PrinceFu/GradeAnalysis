import json as _json
from sqlalchemy import Column, Integer, Float, String, ForeignKey, UniqueConstraint, DateTime, func
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


class ConversionTemplate(Base):
    """赋分模板，存储用户自定义的等级人数占比"""
    __tablename__ = "conversion_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, comment="模板名称")
    tier_ratios = Column(String(2000), nullable=False, comment='各科目各等级人数占比JSON，如{"化学":{"A":15,"B":35,"C":35,"D":13,"E":2},"生物":{...},"政治":{...},"地理":{...}}')
    created_at = Column(DateTime, server_default=func.now())

    @property
    def ratios_dict(self) -> dict:
        return _json.loads(self.tier_ratios)


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
