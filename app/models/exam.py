from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    exam_date = Column(Date, nullable=False)
    exam_type = Column(String(20), nullable=False, comment="模考/月考/期中/期末")

    subjects = relationship("ExamSubject", back_populates="exam", cascade="all, delete-orphan")


class ExamSubject(Base):
    __tablename__ = "exam_subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    subject = Column(String(10), nullable=False)
    full_score = Column(Integer, nullable=False, comment="满分值")
    needs_conversion = Column(Boolean, default=False, comment="是否需要等级赋分")

    exam = relationship("Exam", back_populates="subjects")
    scores = relationship("Score", back_populates="exam_subject")

    __table_args__ = (
        {"comment": "考试科目，每个考试×每个科目一行"},
    )
