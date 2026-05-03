from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from app.database import get_db
from app.config import BASE_DIR

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(name="index.html", request=request)


@router.get("/students", response_class=HTMLResponse)
def students_page(request: Request):
    return templates.TemplateResponse(name="students/list.html", request=request)


@router.get("/students/{student_id}", response_class=HTMLResponse)
def student_detail_page(request: Request, student_id: int):
    return templates.TemplateResponse(name="students/detail.html", request=request, context={"student_id": student_id})


@router.get("/exams", response_class=HTMLResponse)
def exams_page(request: Request):
    return templates.TemplateResponse(name="exams/list.html", request=request)


@router.get("/exams/{exam_id}", response_class=HTMLResponse)
def exam_detail_page(request: Request, exam_id: int):
    return templates.TemplateResponse(name="exams/detail.html", request=request, context={"exam_id": exam_id})


@router.get("/scores/entry", response_class=HTMLResponse)
def score_entry_page(request: Request):
    return templates.TemplateResponse(name="scores/entry.html", request=request)


@router.get("/analysis/grade", response_class=HTMLResponse)
def grade_analysis_page(request: Request):
    return templates.TemplateResponse(name="analysis/grade.html", request=request)


@router.get("/analysis/class", response_class=HTMLResponse)
def class_analysis_page(request: Request):
    return templates.TemplateResponse(name="analysis/class.html", request=request)


@router.get("/analysis/subject", response_class=HTMLResponse)
def subject_analysis_page(request: Request):
    return templates.TemplateResponse(name="analysis/subject.html", request=request)


@router.get("/analysis/longitudinal", response_class=HTMLResponse)
def longitudinal_page(request: Request):
    return templates.TemplateResponse(name="analysis/longitudinal.html", request=request)
