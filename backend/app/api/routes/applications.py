"""Applications — the tracker + connected workspace. All user-scoped."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.db.models import APPLICATION_STATUSES
from app.schemas.application import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationUpdate,
    FromUrlIn,
    ResumeVersionOut,
    TailorIn,
)
from app.schemas.submission import (
    PrepareIn,
    ReconcileIn,
    SubmitIn,
    submission_out,
)
from app.services import ApplicationService, ResumeService
from app.submissions.service import (
    MANUAL_HANDOFF_INSTRUCTION,
    SubmissionError,
    SubmissionService,
    build_package,
)
from app.submissions.adapters import available_adapters
from app.workflows.service import TaskService

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _svc(db: Session, user: models.User) -> ApplicationService:
    return ApplicationService(db, user)


def _out(obj: models.Application) -> dict:
    return {
        "id": obj.id, "company": obj.company, "role": obj.role, "location": obj.location,
        "job_url": obj.job_url, "date_saved": obj.date_saved, "date_applied": obj.date_applied,
        "status": obj.status, "salary": obj.salary, "ats_score": obj.ats_score,
        "resume_version_id": obj.resume_version_id, "interview_date": obj.interview_date,
        "next_step": obj.next_step, "notes": obj.notes, "jd_analysis": obj.jd_analysis,
        "raw_jd": obj.raw_jd,
        "status_history": obj.status_history or [],
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _version_out(v: models.ResumeVersion) -> dict:
    return {
        "id": v.id, "resume_id": v.resume_id, "application_id": v.application_id,
        "label": v.label, "missing_keywords": v.missing_keywords or [],
        "ats_score": v.ats_score,
        "edited_manually": bool(v.edited_manually),
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.get("/statuses")
def list_statuses():
    return {"statuses": list(APPLICATION_STATUSES)}


@router.get("/submission-adapters")
def submission_adapter_capabilities():
    """Report configured send and manual handoff capabilities."""
    return [
        {"kind": adapter.name, "live": adapter.live, "reason": adapter.reason}
        for adapter in available_adapters()
    ]


@router.post("", status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    try:
        obj = _svc(db, user).create(**payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _out(obj)


@router.get("")
def list_applications(status: str | None = Query(default=None),
                      search: str | None = Query(default=None),
                      sort: str = Query(default="updated"),
                      page: int | None = Query(default=None, ge=1),
                      page_size: int = Query(default=20, ge=1, le=100),
                      db: Session = Depends(get_db),
                      user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    if page is None:
        # Legacy shape (bare array) — default UI path, unchanged.
        return [_out(o) for o in svc.list(status=status, search=search, sort=sort)]
    items = svc.list(status=status, search=search, sort=sort,
                     limit=page_size, offset=(page - 1) * page_size)
    return {
        "items": [_out(o) for o in items],
        "total": svc.count(status=status, search=search),
        "page": page,
        "page_size": page_size,
    }


@router.post("/from-url", status_code=201)
def create_from_url(payload: FromUrlIn, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    """Ingest a live job posting URL into a fully analyzed application."""
    try:
        obj = _svc(db, user).create_from_url(
            payload.url, company=payload.company, role=payload.role,
            location=payload.location,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return _out(obj)


@router.get("/{app_id}")
def get_application(app_id: str, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    data = _svc(db, user).latest(app_id)
    if not data:
        raise HTTPException(status_code=404, detail="application not found")
    return {
        "application": _out(data["application"]),
        "attached_version": _version_out(data["attached_version"]) if data["attached_version"] else None,
        "versions": [_version_out(v) for v in data["versions"]],
        "ats_history": [
            {"id": a.id, "score": a.score, "breakdown": a.breakdown,
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in data["ats_history"]
        ],
        "interview_preps": [
            {"id": p.id, "plan": p.plan,
             "created_at": p.created_at.isoformat() if p.created_at else None}
            for p in data["interview_preps"]
        ],
        "research": [
            {"id": r.id, "name": r.name, "website": r.website, "profile": r.profile,
             "sources": r.sources or []}
            for r in data["research"]
        ],
    }


@router.patch("/{app_id}")
def update_application(app_id: str, payload: ApplicationUpdate, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    try:
        obj = _svc(db, user).update(app_id, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    return _out(obj)


@router.delete("/{app_id}", status_code=204)
def delete_application(app_id: str, db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    if not _svc(db, user).delete(app_id):
        raise HTTPException(status_code=404, detail="application not found")


@router.post("/{app_id}/analyze-jd")
def analyze_jd(app_id: str, db: Session = Depends(get_db),
               user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    try:
        return svc.analyze_jd(obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{app_id}/match-report")
def match_report(app_id: str, resume_version_id: str | None = None,
                 db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    """Transparent JD-requirement -> resume-evidence mapping.

    Uses the attached (or given) tailored version; falls back to the
    application's raw JD analysis when no version exists.
    """
    from app.analysis.keywords import analyze_jd, tokenize

    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    if not obj.raw_jd.strip():
        raise HTTPException(status_code=400, detail="this application has no job description")
    evidence_text = ""
    if resume_version_id:
        v = ResumeService(db, user).get_version(resume_version_id)
        if v is None:
            raise HTTPException(status_code=404, detail="resume version not found")
        evidence_text = v.content or ""
    elif obj.resume_version_id:
        v = ResumeService(db, user).get_version(obj.resume_version_id)
        evidence_text = (v.content if v else "") or ""
    jd = analyze_jd(obj.raw_jd)
    ev_lines = [l for l in evidence_text.splitlines() if l.strip()]
    rows = []
    for skill in jd["skills"]:
        hits = [l.strip()[:200] for l in ev_lines if skill in set(tokenize(l))]
        rows.append({"requirement": skill, "status": "matched" if hits else "missing",
                     "evidence": hits[:3]})
    for kw in jd["keywords"][:15]:
        if kw["term"] in {r["requirement"] for r in rows}:
            continue
        hits = [l.strip()[:200] for l in ev_lines if kw["term"] in set(tokenize(l))]
        rows.append({"requirement": kw["term"], "status": "matched" if hits else "missing",
                     "evidence": hits[:3]})
    matched = sum(1 for r in rows if r["status"] == "matched")
    return {"application_id": app_id, "rows": rows,
            "coverage": round(matched / len(rows), 3) if rows else 0.0}


@router.post("/{app_id}/tailor", status_code=201)
def tailor_resume(app_id: str, payload: TailorIn, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    resume = ResumeService(db, user).get(payload.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="resume not found")
    try:
        version = svc.tailor(obj, resume, payload.label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    svc.attach_version(obj, version)  # tailored version auto-attaches to its application
    return _version_out(version)


@router.post("/{app_id}/attach-version")
def attach_version(app_id: str, payload: dict, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    version = ResumeService(db, user).get_version(payload.get("resume_version_id", ""))
    if version is None:
        raise HTTPException(status_code=404, detail="resume version not found")
    try:
        return _out(svc.attach_version(obj, version))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{app_id}/ats", status_code=201)
def run_ats(app_id: str, payload: dict, db: Session = Depends(get_db),
            user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    rsvc = ResumeService(db, user)
    text, version_id = "", None
    if payload.get("resume_version_id"):
        v = rsvc.get_version(payload["resume_version_id"])
        if v is None:
            raise HTTPException(status_code=404, detail="resume version not found")
        text, version_id = v.content, v.id
    elif payload.get("resume_id"):
        r = rsvc.get(payload["resume_id"])
        if r is None:
            raise HTTPException(status_code=404, detail="resume not found")
        text = r.raw_text
    else:
        attached = db.get(models.ResumeVersion, obj.resume_version_id) if obj.resume_version_id else None
        if attached is None or attached.user_id != user.id:
            raise HTTPException(status_code=400, detail="no resume attached — attach a version or pass resume_id")
        text, version_id = attached.content, attached.id
    try:
        row = svc.run_ats(obj, text, version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": row.id, "score": row.score, "breakdown": row.breakdown}


@router.post("/{app_id}/ats-v2", status_code=201)
def run_ats_v2(app_id: str, payload: dict, db: Session = Depends(get_db),
               user: models.User = Depends(get_current_user)):
    """Job-specific ATS v2: staged matching, configurable weights, unknown
    categories excluded. Optional body: {resume_id?, resume_version_id?, weights?}."""
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    rsvc = ResumeService(db, user)
    text, version_id, parsed_doc = "", None, None
    if payload.get("resume_version_id"):
        v = rsvc.get_version(payload["resume_version_id"])
        if v is None:
            raise HTTPException(status_code=404, detail="resume version not found")
        text, version_id = v.content, v.id
    elif payload.get("resume_id"):
        r = rsvc.get(payload["resume_id"])
        if r is None:
            raise HTTPException(status_code=404, detail="resume not found")
        text, parsed_doc = r.raw_text, r.parsed_doc
    else:
        attached = db.get(models.ResumeVersion, obj.resume_version_id) if obj.resume_version_id else None
        if attached is None or attached.user_id != user.id:
            raise HTTPException(status_code=400, detail="no resume attached — attach a version or pass resume_id")
        text, version_id = attached.content, attached.id
    weights = payload.get("weights")
    if weights is not None and (not isinstance(weights, dict) or not weights):
        raise HTTPException(status_code=400, detail="weights must be a non-empty object")
    try:
        row = svc.run_ats_v2(obj, text, parsed_doc, version_id, weights)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": row.id, "score": row.score, "breakdown": row.breakdown}


@router.post("/{app_id}/interview-prep", status_code=201)
def interview_prep(app_id: str, payload: dict, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    resume_text = ""
    if payload.get("resume_id"):
        r = ResumeService(db, user).get(payload["resume_id"])
        resume_text = r.raw_text if r else ""
    try:
        row = svc.run_interview_prep(obj, resume_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": row.id, "plan": row.plan}


@router.post("/{app_id}/company-research", status_code=201)
def company_research(app_id: str, payload: dict, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    svc = _svc(db, user)
    obj = svc.get(app_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="application not found")
    try:
        row = svc.run_company_research(obj, (payload.get("website") or "").strip() or None)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"id": row.id, "name": row.name, "website": row.website,
            "profile": row.profile, "sources": row.sources or []}


@router.get("/versions/all")
def list_versions(application_id: str | None = None, db: Session = Depends(get_db),
                  user: models.User = Depends(get_current_user)):
    return [_version_out(v) for v in ResumeService(db, user).list_versions(application_id)]


@router.get("/versions/{version_id}")
def get_version(version_id: str, db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    v = ResumeService(db, user).get_version(version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="resume version not found")
    out = _version_out(v)
    out["content"] = v.content
    out["changes"] = v.changes or []
    return out


@router.patch("/versions/{version_id}")
def update_version(version_id: str, payload: dict, db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    """Edit a tailored version's label or content. Content edits are flagged
    (edited_manually) since they bypass the evidence-preserving tailor."""
    v = ResumeService(db, user).get_version(version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="resume version not found")
    if "label" in payload and payload["label"] is not None:
        v.label = str(payload["label"])[:512]
    if "content" in payload and payload["content"] is not None:
        content = str(payload["content"])
        if not content.strip():
            raise HTTPException(status_code=400, detail="content must not be empty")
        if content != v.content:
            v.content = content[:100_000]
            v.edited_manually = True
            # The manual edit supersedes everything derived from the edited
            # text: analyses for this version are stale, and optimization runs
            # whose final version was edited describe a superseded document.
            db.query(models.ATSAnalysis).filter_by(
                user_id=user.id, resume_version_id=v.id).update({"stale": True})
            db.query(models.OptimizationRun).filter_by(
                user_id=user.id, final_version_id=v.id).update({"invalidated": True})
    db.commit()
    db.refresh(v)
    out = _version_out(v)
    out["content"] = v.content
    out["changes"] = v.changes or []
    return out


@router.get("/versions/{version_id}/compare")
def compare_version(version_id: str, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    """Line-level diff: master resume vs tailored version (extractive-proof)."""
    import difflib

    v = ResumeService(db, user).get_version(version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="resume version not found")
    master_lines = []
    if v.resume_id:
        master = ResumeService(db, user).get(v.resume_id)
        if master:
            master_lines = master.raw_text.splitlines()
    tailored_lines = (v.content or "").splitlines()
    sm = difflib.SequenceMatcher(a=master_lines, b=tailored_lines, autojunk=False)
    return {
        "version_id": v.id,
        "resume_id": v.resume_id,
        "same_line_set": sorted(master_lines) == sorted(tailored_lines),
        "added": [l for l in tailored_lines if l not in master_lines],
        "removed": [l for l in master_lines if l not in tailored_lines],
        "similarity": round(sm.ratio(), 4),
        "unified_diff": list(difflib.unified_diff(
            master_lines, tailored_lines, fromfile="master", tofile="tailored", lineterm="",
        ))[:400],
    }


@router.get("/versions/{version_id}/pdf")
def version_pdf(version_id: str, db: Session = Depends(get_db),
                user: models.User = Depends(get_current_user)):
    """Export a tailored version as PDF (plain-text layout, ATS-safe fonts).

    The export is reparsed and validated for readability before it is sent:
    an unreadable PDF is never returned, it becomes a 500 instead."""
    from fastapi.responses import Response

    from app.resume.pdf import render_resume_pdf, validate_pdf_export

    v = ResumeService(db, user).get_version(version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="resume version not found")
    pdf = render_resume_pdf(v.label, v.content or "")
    validation = validate_pdf_export(pdf, v.content or "")
    if not validation["readable"]:
        raise HTTPException(status_code=500, detail=(
            "exported PDF failed readability validation; export withheld: "
            f"{validation.get('error', 'line coverage too low')}"))
    safe = "".join(c for c in v.label if c.isalnum() or c in " _-").strip()[:60] or "resume"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'})


# --------------------------------------------------------------------------- #
# Submissions (step 07): frozen packages -> adapters -> receipts.
# Only a confirmed receipt marks the application applied; the manual tracker
# below stays exactly as it was.

def _submission_error(err: "SubmissionError") -> HTTPException:
    detail = {"code": err.code, "detail": err.detail}
    if err.code in (
        "application_not_found",
        "submission_not_found",
        "resume_not_found",
    ):
        return HTTPException(status_code=404, detail=detail)
    if err.code == "idempotency_conflict":
        return HTTPException(status_code=409, detail=detail)
    if err.code == "not_reconcilable":
        return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=422, detail=detail)


@router.post("/{app_id}/prepare")
def prepare_submission(app_id: str, payload: PrepareIn,
                       db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    """Validate + preview the frozen package without queueing anything.

    Unknown mandatory answers come back as ``needs_input`` with the list; an
    unsupported destination comes back with an actionable manual handoff."""
    svc = SubmissionService(db, user.id)
    app_obj = svc._get_owned(models.Application, app_id)
    if app_obj is None:
        raise HTTPException(status_code=404, detail={"code": "application_not_found", "detail": "application not found"})
    destination = payload.destination_url or app_obj.job_url or ""
    try:
        built = build_package(
            db, user.id, app_obj,
            answers=payload.answers,
            destination_url=destination,
            resume_version_id=payload.resume_version_id,
            questions=[q.model_dump() for q in payload.questions] if payload.questions else None,
            adapter_kind=payload.adapter,
        )
    except SubmissionError as err:
        raise _submission_error(err) from None
    adapter = built["adapter"]
    handoff = None
    if built["adapter_kind"] == "manual":
        handoff = {
            "url": built["package"]["destination_url"],
            "instruction": MANUAL_HANDOFF_INSTRUCTION,
        }
    return {
        "application_id": app_id,
        "adapter": {"kind": adapter.name, "live": adapter.live, "reason": adapter.reason},
        "destination_url": built["package"]["destination_url"],
        "questions": built["package"]["form"],
        "answers": built["package"]["answers"],
        "missing_required": built["missing"],
        "package_sha256": built["package_sha256"],
        "artifact_sha256": built["artifact_sha256"],
        "artifact_preview": (built["artifact_text"] or "")[:2000],
        "state": built["state"],
        "handoff": handoff,
    }


@router.post("/{app_id}/submit", status_code=202)
def submit_application(app_id: str, payload: SubmitIn,
                       db: Session = Depends(get_db),
                       user: models.User = Depends(get_current_user)):
    """Queue an authorized submission of a validated package.

    Repeated identical requests replay; a different package under the same
    idempotency key conflicts. The worker re-checks authorization, package
    hash and artifact hash immediately before contacting the destination."""
    svc = SubmissionService(db, user.id)
    try:
        sub, task, replayed = svc.queue_submission(
            app_id,
            answers=payload.answers,
            destination_url=payload.destination_url,
            resume_version_id=payload.resume_version_id,
            questions=[q.model_dump() for q in payload.questions] if payload.questions else None,
            idempotency_key=payload.idempotency_key,
            ttl_seconds=payload.ttl_seconds,
        )
    except SubmissionError as err:
        raise _submission_error(err) from None
    poll_url = f"/api/tasks/{task.id}" if task is not None else ""
    return {
        "submission_id": sub.id,
        "task_id": sub.task_id,
        "status": task.status if task is not None else sub.state,
        "poll_url": poll_url,
        "replayed": bool(replayed),
        "state": sub.state,
    }


@router.get("/{app_id}/submissions")
def list_submissions(app_id: str, db: Session = Depends(get_db),
                     user: models.User = Depends(get_current_user)):
    """Submission history, receipts and handoff information for one application."""
    svc = SubmissionService(db, user.id)
    app_obj = svc._get_owned(models.Application, app_id)
    if app_obj is None:
        raise HTTPException(status_code=404, detail={"code": "application_not_found", "detail": "application not found"})
    subs = svc.list_for(app_id)
    return {
        "application_id": app_id,
        "submissions": [submission_out(s) for s in subs],
        "total": len(subs),
    }


@router.get("/{app_id}/submissions/{submission_id}")
def get_submission(app_id: str, submission_id: str,
                   db: Session = Depends(get_db),
                   user: models.User = Depends(get_current_user)):
    svc = SubmissionService(db, user.id)
    sub = svc.get(submission_id)
    if sub is None or sub.application_id != app_id:
        raise HTTPException(status_code=404, detail={"code": "submission_not_found", "detail": "submission not found"})
    return submission_out(sub)


@router.post("/{app_id}/submissions/{submission_id}/reconcile")
def reconcile_submission(app_id: str, submission_id: str, payload: ReconcileIn,
                         db: Session = Depends(get_db),
                         user: models.User = Depends(get_current_user)):
    """Resolve an ambiguous (``unknown``) submission. Never re-sends: asks the
    destination about this exact submission id, or records its affirmative
    non-receipt as ``failed``."""
    svc = SubmissionService(db, user.id)
    owned = svc.get(submission_id)
    if owned is None or owned.application_id != app_id:
        raise HTTPException(status_code=404, detail={"code": "submission_not_found", "detail": "submission not found"})
    try:
        sub = svc.reconcile(submission_id, payload.outcome)
    except SubmissionError as err:
        raise _submission_error(err) from None
    if sub.state == "submitted":
        resolution = "submitted"
    elif sub.state == "failed" and "no record" in (sub.state_reason or ""):
        resolution = "not_found"
    elif sub.state == "failed":
        resolution = "failed"
    elif sub.state == "unknown":
        resolution = "still_unknown"
    else:
        resolution = sub.state
    return {
        "submission_id": sub.id,
        "state": sub.state,
        "resolution": resolution,
        "note": sub.state_reason or "",
    }


@router.post("/{app_id}/submissions/{submission_id}/cancel")
def cancel_submission(app_id: str, submission_id: str,
                      db: Session = Depends(get_db),
                      user: models.User = Depends(get_current_user)):
    """Cancel a queued submission before any external effect. A confirmed
    submission cannot be cancelled here."""
    svc = SubmissionService(db, user.id)
    sub = svc.get(submission_id)
    if sub is None or sub.application_id != app_id:
        raise HTTPException(status_code=404, detail={"code": "submission_not_found", "detail": "submission not found"})
    svc.cancel_queued(sub, "cancelled by user")
    if sub.task_id:
        try:
            TaskService(db, user.id).cancel(sub.task_id)
        except LookupError:
            pass
    return submission_out(sub)
