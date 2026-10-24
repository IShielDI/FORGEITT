"""Behavioural tests for model defaults and database constraints."""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.models import (
    Approval,
    CheckResult,
    Contract,
    Failure,
    Job,
    KnowledgeLink,
    Member,
    Message,
    SpecItem,
    SpecVersion,
    Submission,
    Task,
    User,
    Workspace,
)
from app.models.enums import (
    ApprovalDecision,
    CheckKind,
    CheckStatus,
    ContractKind,
    ContractStatus,
    EntityType,
    JobStatus,
    MemberRole,
    SpecItemKind,
    SpecItemStatus,
    SubmissionStatus,
    TaskStatus,
    VerificationProfile,
)
from tests.factories import make_run, make_task, make_user, make_workspace


def test_workspace_defaults(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    db_session.refresh(workspace)

    assert isinstance(workspace.id, uuid.UUID)
    assert workspace.verification_profile is VerificationProfile.LIGHT
    assert workspace.created_at is not None


def test_room_code_is_unique(db_session: Session) -> None:
    first = make_workspace(db_session)
    db_session.add(Workspace(room_code=first.room_code, name="Dup", owner_id=first.owner_id))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_member_unique_per_workspace(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    user = make_user(db_session, "Bo")
    db_session.add(Member(workspace_id=workspace.id, user_id=user.id, role=MemberRole.OWNER))
    db_session.flush()
    db_session.add(Member(workspace_id=workspace.id, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_spec_item_starts_proposed_at_version_one(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    message = Message(workspace_id=workspace.id, user_id=workspace.owner_id, body="Use Postgres")
    db_session.add(message)
    db_session.flush()
    item = SpecItem(
        workspace_id=workspace.id,
        kind=SpecItemKind.SUGGESTION,
        text="Use Postgres",
        source_message_ids=[message.id],
    )
    db_session.add(item)
    db_session.flush()
    db_session.refresh(item)

    assert item.status is SpecItemStatus.PROPOSED
    assert item.version == 1
    assert item.source_message_ids == [message.id]
    assert item.confirmed_by is None


def test_invalid_enum_value_is_rejected(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    db_session.add(SpecItem(workspace_id=workspace.id, kind="opinion", text="x"))

    with pytest.raises(StatementError):
        db_session.flush()


def test_spec_version_numbers_unique_per_workspace(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    db_session.add(SpecVersion(workspace_id=workspace.id, version=1, snapshot_json={"items": []}))
    db_session.flush()
    db_session.add(SpecVersion(workspace_id=workspace.id, version=1))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_contract_versions_are_separate_rows(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    for version in (1, 2):
        db_session.add(
            Contract(
                workspace_id=workspace.id,
                kind=ContractKind.API,
                name="openapi",
                content=f"v{version}",
                version=version,
            )
        )
    db_session.flush()

    rows = db_session.scalars(select(Contract).where(Contract.workspace_id == workspace.id)).all()
    assert sorted(c.version for c in rows) == [1, 2]
    assert all(c.status is ContractStatus.PROPOSED for c in rows)


def test_version_must_be_positive(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    db_session.add(
        Contract(workspace_id=workspace.id, kind=ContractKind.TYPE, name="t", content="", version=0)
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_task_arrays_default_empty(db_session: Session) -> None:
    task = make_task(db_session, make_workspace(db_session))
    db_session.refresh(task)

    assert task.status is TaskStatus.PROPOSED
    assert task.depends_on == []
    assert task.contract_ids == []


def test_knowledge_link_round_trip(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    task = make_task(db_session, workspace)
    req_id = uuid.uuid4()
    db_session.add(
        KnowledgeLink(
            workspace_id=workspace.id,
            src_type=EntityType.REQUIREMENT,
            src_id=req_id,
            dst_type=EntityType.TASK,
            dst_id=task.id,
            relation="implemented_by",
        )
    )
    db_session.flush()

    link = db_session.scalars(select(KnowledgeLink).where(KnowledgeLink.src_id == req_id)).one()
    assert link.dst_type is EntityType.TASK
    assert link.version == 1


def test_submission_and_check_result_defaults(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    submission = Submission(task_id=make_task(db_session, workspace).id, commit_sha="b" * 40)
    check = CheckResult(
        run_id=make_run(db_session, workspace).id, name="pytest", kind=CheckKind.UNIT_TEST
    )
    db_session.add_all([submission, check])
    db_session.flush()
    db_session.refresh(submission)
    db_session.refresh(check)

    assert submission.status is SubmissionStatus.PENDING
    assert check.status is CheckStatus.PENDING
    assert check.exit_code is None
    assert check.artifacts_json == {}


@pytest.mark.parametrize("confidence", [-0.1, 1.5])
def test_failure_confidence_must_be_between_zero_and_one(
    db_session: Session, confidence: float
) -> None:
    run = make_run(db_session, make_workspace(db_session))
    db_session.add(Failure(run_id=run.id, confidence=confidence))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_rejected_approval_cannot_record_a_merge(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    run = make_run(db_session, workspace)
    db_session.add(
        Approval(
            run_id=run.id,
            approver_id=workspace.owner_id,
            decision=ApprovalDecision.REJECTED,
            candidate_sha="c" * 40,
            merged_sha="d" * 40,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_job_defaults(db_session: Session) -> None:
    job = Job(type="integration_run", payload={"run_id": "x"})
    db_session.add(job)
    db_session.flush()
    db_session.refresh(job)

    assert job.status is JobStatus.QUEUED
    assert job.attempts == 0


def test_deleting_workspace_cascades_to_children(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    db_session.add(Message(workspace_id=workspace.id, user_id=workspace.owner_id, body="hi"))
    make_task(db_session, workspace)
    db_session.flush()

    db_session.delete(workspace)
    db_session.flush()

    assert db_session.scalar(select(func.count()).select_from(Message)) == 0
    assert db_session.scalar(select(func.count()).select_from(Task)) == 0


def test_user_with_workspace_cannot_be_deleted(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    owner = db_session.get(User, workspace.owner_id)
    assert owner is not None

    db_session.delete(owner)
    with pytest.raises(IntegrityError):
        db_session.flush()
