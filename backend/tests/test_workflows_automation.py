"""Authorization surface — approvals, policies, quotas, revocation (SQLite).

A fake side-effecting handler is registered to exercise the owner-scope +
approval + policy validation path that real external actions will take.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.workflows import models as wf
from app.workflows.clock import utcnow
from app.workflows.executor import execute
from app.workflows.handlers import register
from app.workflows.handlers import TaskFailure
from app.workflows.service import TaskService
from app.workflows.automation import (
    AutomationError,
    AutomationService,
)

PROBE_KIND = "tests.probe_send"

_holder = {"used": 0}


def _probe(payload, ctx):
    _holder["used"] += 1
    data = payload or {}
    marker = data.get("marker", "")
    fail_times = int(data.get("fail_times", 0) or 0)
    if fail_times and _holder["used"] < fail_times:
        raise TaskFailure("tests.probe_transient", "injected probe transient failure")
    return {"sent": True, "marker": marker}


register(PROBE_KIND, external_side_effect=True, summary="test-only side-effecting action")(_probe)


@pytest.fixture(autouse=True)
def _probe_handler():
    _holder["used"] = 0
    return _holder


@pytest.fixture()
def db(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'wf.db'}", connect_args={"check_same_thread": False})
    import app.db.models  # noqa: F401
    import app.workflows.models  # noqa: F401
    from app.db.database import Base

    Base.metadata.create_all(eng)
    TestingSession = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    session = TestingSession()
    session.add(models.User(username="u1", password_hash="x"))
    session.add(models.User(username="u2", password_hash="x"))
    session.commit()
    return session


def _task(db, kind, payload, **kw):
    user = db.query(models.User).filter_by(username="u1").one()
    task, _ = TaskService(db, user.id).enqueue(kind, payload, **kw)
    return task


def _policy(db, **overrides):
    user = db.query(models.User).filter_by(username="u1").one()
    args = dict(
        name="p",
        allowed_actions=[PROBE_KIND],
        constraints={"daily_limit": 5},
    )
    args.update(overrides)
    return AutomationService(db, user.id).create_policy(**args)


def _approval(db, kind=PROBE_KIND, payload=None, **kw):
    user = db.query(models.User).filter_by(username="u1").one()
    return AutomationService(db, user.id).create_approval(
        action_kind=kind,
        payload=payload if payload is not None else {"marker": "m1"},
        **kw,
    )


# --------------------------------------------------------------------------- #
# Approvals: exact payload binding, single use to one task, expiry

def test_side_effect_requires_grant_area_approval(db):
    task = _task(db, PROBE_KIND, {"marker": "m1"})
    result = execute(db, task.id)
    assert result["outcome"] == "failed"
    row = db.query(wf.TaskRun).filter_by(id=task.id).one()
    assert row.error_code == "no_active_authorization"


def test_approval_grants_execution_and_binds_task(db, _probe_handler):
    task = _task(db, PROBE_KIND, {"marker": "m1"})
    _approval(db)
    result = execute(db, task.id)
    assert result["outcome"] == "succeeded", result
    assert _probe_handler["used"] == 1
    approval = db.query(wf.ActionApproval).one()
    assert approval.task_id == task.id and approval.used_at is not None


def test_approval_is_worthless_to_other_tasks(db):
    task = _task(db, PROBE_KIND, {"marker": "m1"})
    other = _task(db, PROBE_KIND, {"marker": "m1"})
    _approval(db)
    assert execute(db, task.id)["outcome"] == "succeeded"
    second = execute(db, other.id)
    assert second["outcome"] == "failed"
    row = db.query(wf.TaskRun).filter_by(id=other.id).one()
    assert row.error_code == "approval_used_by_other_task"


def test_approval_payload_hash_mismatch_denied(db):
    task = _task(db, PROBE_KIND, {"marker": "different"})
    _approval(db)
    result = execute(db, task.id)
    assert result["outcome"] == "failed"
    row = db.query(wf.TaskRun).filter_by(id=task.id).one()
    assert row.error_code in {"needs_approval", "no_active_authorization"}


def test_revoked_approval_denied(db):
    task = _task(db, PROBE_KIND, {"marker": "m1"})
    approval = _approval(db)
    AutomationService(db,approval.user_id).revoke_approval(approval.id)
    result = execute(db, task.id)
    assert result["outcome"] == "failed"
    row = db.query(wf.TaskRun).filter_by(id=task.id).one()
    assert row.error_code == "no_active_authorization"


def test_expired_approval_denied(db):
    task = _task(db, PROBE_KIND, {"marker": "m1"})
    past = utcnow()
    approval = _approval(db)
    db.query(wf.ActionApproval).filter_by(id=approval.id).update({"expires_at": past})
    db.commit()
    result = execute(db, task.id)
    assert result["outcome"] == "failed"
    row = db.query(wf.TaskRun).filter_by(id=task.id).one()
    assert row.error_code == "no_active_authorization"


# --------------------------------------------------------------------------- #
# Policies: granting reusable standing authorization

def test_policy_grants_reusable_authorization(db, _probe_handler):
    task = _task(db, PROBE_KIND, {"marker": "p1"})
    other = _task(db, PROBE_KIND, {"marker": "p2"})
    _policy(db)
    assert execute(db, task.id)["outcome"] == "succeeded"
    assert execute(db, other.id)["outcome"] == "succeeded"
    assert _probe_handler["used"] == 2


def test_revoke_policy_blocks_retry_attempts(db):  # revoked standing policy is respected
    task, _ = TaskService(
        db, db.query(models.User).filter_by(username="u1").one().id
    ).enqueue(PROBE_KIND, {"marker": "m1", "fail_times": 2}, max_attempts=5)
    _policy(db)  # first attempt grants via policy
    first = execute(db, task.id)
    assert first["outcome"] == "retry_scheduled", first
    db.query(wf.AutomationPolicy).update({"status": "revoked", "revoked_at": utcnow()})
    db.commit()
    db.query(wf.TaskRun).filter_by(id=task.id).update({"next_attempt_at": utcnow()})
    db.commit()
    second = execute(db, task.id)
    assert second["outcome"] == "failed", second
    row = db.query(wf.TaskRun).filter_by(id=task.id).one()
    assert row.error_code == "authorization_revoked"  # retry revalidation fires, no silent retry


def test_policy_validation_rules(db):
    user = db.query(models.User).filter_by(username="u1").one()
    svc = AutomationService(db, user.id)
    with pytest.raises(AutomationError):
        svc.create_policy(name="no-limit", allowed_actions=[PROBE_KIND], constraints={})
    with pytest.raises(AutomationError):
        svc.create_policy(name="unknown-kind", allowed_actions=["no.such"], constraints={"daily_limit": 1})
    with pytest.raises(AutomationError):
        svc.create_policy(name="pure-kinds", allowed_actions=["diagnostics.echo"], constraints={"daily_limit": 1})


def test_other_users_approval_is_invisible(db):
    task = _task(db, PROBE_KIND, {"marker": "m1"})
    user2 = db.query(models.User).filter_by(username="u2").one()
    AutomationService(db, user2.id).create_approval(action_kind=PROBE_KIND, payload={"marker": "m1"})
    result = execute(db, task.id)
    assert result["outcome"] == "failed"
    row = db.query(wf.TaskRun).filter_by(id=task.id).one()
    assert row.error_code == "no_active_authorization"
