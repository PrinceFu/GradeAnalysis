from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from app.database import get_db
from app.config import BASE_DIR
from app.routers.auth import require_user

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request, current_user=Depends(require_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse(name="index.html", request=request)


@router.get("/students", response_class=HTMLResponse)
def students_page(request: Request, current_user=Depends(require_user)):
    return templates.TemplateResponse(name="students/list.html", request=request)

@router.get("/students/{student_id}", response_class=HTMLResponse)
def student_detail_page(request: Request, student_id: int, current_user=Depends(require_user)):
    return templates.TemplateResponse(name="students/detail.html", request=request, context={"student_id": student_id})


@router.get("/exams", response_class=HTMLResponse)
def exams_page(request: Request, current_user=Depends(require_user)):
    return templates.TemplateResponse(name="exams/list.html", request=request)


@router.get("/exams/{exam_id}", response_class=HTMLResponse)
def exam_detail_page(request: Request, exam_id: int, current_user=Depends(require_user)):
    return templates.TemplateResponse(name="exams/detail.html", request=request, context={"exam_id": exam_id})


@router.get("/analysis/single/grade", response_class=HTMLResponse)
def grade_analysis_page(request: Request, current_user=Depends(require_user)):
    return templates.TemplateResponse(name="analysis/grade.html", request=request)


@router.get("/analysis/single/class", response_class=HTMLResponse)
def class_analysis_page(request: Request, current_user=Depends(require_user)):
    return templates.TemplateResponse(name="analysis/class.html", request=request)


@router.get("/analysis/single/student", response_class=HTMLResponse)
def student_analysis_page(request: Request, current_user=Depends(require_user)):
    return templates.TemplateResponse(name="analysis/single_student.html", request=request)


@router.get("/analysis/multi", response_class=HTMLResponse)
def multi_exam_page(request: Request, current_user=Depends(require_user)):
    return templates.TemplateResponse(name="analysis/multi_exam.html", request=request)


@router.get("/analysis/tracking", response_class=HTMLResponse)
def tracking_page(request: Request, current_user=Depends(require_user)):
    return templates.TemplateResponse(name="analysis/longitudinal.html", request=request)
