"""Minimal builders for test rows. Each flushes so database defaults and constraints apply."""

import uuid

from sqlalchemy.orm import Session

from app.models import IntegrationRun, Task, User, Workspace
from app.models.enums import VerificationProfile


def make_user(session: Session, name: str = "Ada") -> User:
    user = User(name=name, email=f"{uuid.uuid4().hex[:12]}@example.test")
    session.add(user)
    session.flush()
    return user


def make_workspace(session: Session, owner: User | None = None) -> Workspace:
    owner = owner or make_user(session)
    workspace = Workspace(name="Demo", slug="demo", owner_id=owner.id)
    session.add(workspace)
    session.flush()
    return workspace


def make_task(session: Session, workspace: Workspace, title: str = "Build API") -> Task:
    task = Task(workspace_id=workspace.id, title=title)
    session.add(task)
    session.flush()
    return task


def make_run(session: Session, workspace: Workspace) -> IntegrationRun:
    run = IntegrationRun(
        workspace_id=workspace.id,
        candidate_branch="candidate/test",
        base_sha="a" * 40,
        profile=VerificationProfile.FAST,
    )
    session.add(run)
    session.flush()
    return run
