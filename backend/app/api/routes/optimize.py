"""Resume optimization workflow: master -> ATS -> tailor loop -> LaTeX."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.services import ApplicationService

router = APIRouter(tags=["optimize"])


def _run_out(row: models.OptimizationRun) -> dict:
    return {
        "id": row.id, "application_id": row.application_id, "resume_id": row.resume_id,
        "policy": row.policy or {}, "initial_score": row.initial_score,
        "attempts": row.attempts or [], "final_version_id": row.final_version_id,
        "final_score": row.final_score, "status": row.status,
        "gaps": row.gaps or [], "latex_status": row.latex_status,
        "pdf_ready": bool(row.pdf_path),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/api/applications/{app_id}/optimize", status_code=201)
def run_optimization(app_id: str, payload: dict, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    if not payload.get("resume_id"):
        raise HTTPException(status_code=400, detail="resume_id is required")
    svc = ApplicationService(db, user)
    try:
        return svc.run_optimization(app_id, payload["resume_id"], payload.get("policy"))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/optimize/runs")
def list_runs(application_id: str | None = None, db: Session = Depends(get_db),
              user: models.User = Depends(get_current_user)):
    q = db.query(models.OptimizationRun).filter_by(user_id=user.id)
    if application_id:
        q = q.filter_by(application_id=application_id)
    return [_run_out(r) for r in q.order_by(models.OptimizationRun.created_at.desc()).all()]


@router.get("/api/optimize/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db),
            user: models.User = Depends(get_current_user)):
    row = db.get(models.OptimizationRun, run_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="optimization run not found")
    out = _run_out(row)
    out["stop_reason"] = row.stop_reason
    return out


@router.get("/api/optimize/runs/{run_id}/latex", response_class=PlainTextResponse)
def download_latex(run_id: str, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    row = db.get(models.OptimizationRun, run_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="optimization run not found")
    if not row.final_latex:
        raise HTTPException(status_code=404, detail="no LaTeX source for this run")
    return PlainTextResponse(
        row.final_latex, media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="resume-{run_id[:8]}.tex"'})


@router.get("/api/optimize/runs/{run_id}/pdf")
def download_pdf(run_id: str, db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    from pathlib import Path

    row = db.get(models.OptimizationRun, run_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="optimization run not found")
    # Never present an uncompiled source as a PDF: 404 unless a real file exists.
    if not row.pdf_path or not Path(row.pdf_path).exists():
        raise HTTPException(
            status_code=404,
            detail=f"no compiled PDF for this run (latex status: {row.latex_status or 'unknown'}). "
                   "Download the .tex source and compile with a LaTeX distribution.")
    data = Path(row.pdf_path).read_bytes()
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=500, detail="stored PDF failed validation")
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="resume-{run_id[:8]}.pdf"'})
