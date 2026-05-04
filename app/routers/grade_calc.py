"""
成绩计算 API 路由
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import io

from app.database import get_db
from app.services.grade_calc_service import (
    calculate_grades,
    create_template,
    list_templates,
    get_template,
    update_template,
    delete_template,
    export_grade_results,
)

router = APIRouter()


# ---- 请求模型 ----


class GradeCalcRequest(BaseModel):
    exam_id: int
    use_conversion: bool = False
    template_id: int | None = None


class TemplateCreate(BaseModel):
    name: str
    tier_ratios: dict  # {"化学": {"A":15,"B":35,"C":35,"D":13,"E":2}, "生物": {...}, ...}


class TemplateUpdate(BaseModel):
    name: str | None = None
    tier_ratios: dict | None = None


CONVERSION_SUBJECTS_LIST = ["化学", "生物", "政治", "地理"]


def _validate_per_subject_ratios(tier_ratios: dict) -> str | None:
    """验证按科目分组的等级占比，返回错误信息或 None"""
    for subj in CONVERSION_SUBJECTS_LIST:
        if subj not in tier_ratios:
            return f"缺少科目「{subj}」的等级占比"
        ratios = tier_ratios[subj]
        total = sum(ratios.get(t, 0) for t in ["A", "B", "C", "D", "E"])
        if abs(total - 100) > 0.01:
            return f"科目「{subj}」的等级占比总和必须为100%，当前为{total}%"
    return None


class GradeExportRequest(BaseModel):
    exam_id: int
    use_conversion: bool = False
    template_id: int | None = None
    filter: str = "all"  # "all", "class", "combination"
    filter_value: str | None = None


# ---- 成绩计算 ----


@router.post("/calculate")
def run_grade_calculation(data: GradeCalcRequest, db: Session = Depends(get_db)):
    """执行成绩计算"""
    if data.use_conversion and not data.template_id:
        raise HTTPException(status_code=400, detail="进行赋分计算时必须选择赋分模板")
    try:
        result = calculate_grades(db, data.exam_id, data.use_conversion, data.template_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


# ---- 赋分模板 CRUD ----


@router.get("/templates")
def api_list_templates(db: Session = Depends(get_db)):
    """列出所有赋分模板"""
    templates = list_templates(db)
    return [
        {
            "id": t.id,
            "name": t.name,
            "tier_ratios": t.ratios_dict,
            "created_at": str(t.created_at) if t.created_at else None,
        }
        for t in templates
    ]


@router.post("/templates")
def api_create_template(data: TemplateCreate, db: Session = Depends(get_db)):
    """创建赋分模板"""
    err = _validate_per_subject_ratios(data.tier_ratios)
    if err:
        raise HTTPException(status_code=400, detail=err)
    try:
        tpl = create_template(db, data.name, data.tier_ratios)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建失败: {e}")
    return {"id": tpl.id, "name": tpl.name, "tier_ratios": tpl.ratios_dict}


@router.get("/templates/{template_id}")
def api_get_template(template_id: int, db: Session = Depends(get_db)):
    """获取单个赋分模板"""
    tpl = get_template(db, template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {
        "id": tpl.id,
        "name": tpl.name,
        "tier_ratios": tpl.ratios_dict,
        "created_at": str(tpl.created_at) if tpl.created_at else None,
    }


@router.put("/templates/{template_id}")
def api_update_template(template_id: int, data: TemplateUpdate, db: Session = Depends(get_db)):
    """更新赋分模板"""
    if data.tier_ratios is not None:
        err = _validate_per_subject_ratios(data.tier_ratios)
        if err:
            raise HTTPException(status_code=400, detail=err)
    try:
        tpl = update_template(db, template_id, data.name, data.tier_ratios)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"id": tpl.id, "name": tpl.name, "tier_ratios": tpl.ratios_dict}


@router.delete("/templates/{template_id}")
def api_delete_template(template_id: int, db: Session = Depends(get_db)):
    """删除赋分模板"""
    try:
        delete_template(db, template_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


# ---- 导出 ----


@router.post("/export")
def api_export_results(data: GradeExportRequest, db: Session = Depends(get_db)):
    """导出成绩计算结果为 Excel"""
    if data.use_conversion and not data.template_id:
        raise HTTPException(status_code=400, detail="进行赋分计算时必须选择赋分模板")
    try:
        file_data = export_grade_results(
            db, data.exam_id, data.use_conversion, data.template_id,
            data.filter, data.filter_value,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not file_data:
        raise HTTPException(status_code=404, detail="暂无数据可导出")

    filename = f"grade_calc_{data.exam_id}.xlsx"
    return StreamingResponse(
        io.BytesIO(file_data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
