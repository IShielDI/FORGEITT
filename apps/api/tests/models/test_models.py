"""Behavioural tests for model defaults and database constraints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.models import (
    Approval,
    CheckResult,
    Contract,
    CreditLedger,
    Failure,
    HiddenTest,
    Invite,
    Job,
    KnowledgeLink,
    Member,
    Message,
    RefereeRun,
    SpecItem,
    SpecVersion,
    Submission,
    Task,
    User,
)
from app.models.enums import (
    ApprovalDecision,
    CheckKind,
    CheckStatus,
    ContractKind,
    ContractStatus,
    CreditKind,
    EntityType,
    HiddenTestStatus,
    JobStatus,
    MemberRole,
    RefereeVerdict,
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

    assert len(workspace.id) == 36
    assert workspace.verification_profile is VerificationProfile.FAST
    assert workspace.allowed_providers == []
    assert workspace.created_at is not None


def test_member_unique_per_workspace_and_viewer_role(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    user = make_user(db_session, "Bo")
    db_session.add(Member(workspace_id=workspace.id, user_id=user.id, role=MemberRole.VIEWER))
    db_session.flush()
    db_session.add(Member(workspace_id=workspace.id, user_id=user.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_member_token_hash_is_unique(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    first, second = make_user(db_session, "A"), make_user(db_session, "B")
    for user in (first, second):
        db_session.add(Member(workspace_id=workspace.id, user_id=user.id, token_hash="f" * 64))

    with pytest.raises(IntegrityError):
        db_session.flush()


def _invite(workspace_id: str, created_by: str, token_hash: str = "e" * 64) -> Invite:
    return Invite(
        workspace_id=workspace_id,
        token_hash=token_hash,
        created_by=created_by,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )


def test_invite_defaults_and_unique_token_hash(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    invite = _invite(workspace.id, workspace.owner_id)
    db_session.add(invite)
    db_session.flush()
    db_session.refresh(invite)

    assert invite.role is MemberRole.MEMBER
    assert invite.used_at is None

    db_session.add(_invite(workspace.id, workspace.owner_id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invite_used_at_requires_used_by(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    invite = _invite(workspace.id, workspace.owner_id)
    invite.used_at = datetime.now(UTC)
    db_session.add(invite)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_spec_item_starts_proposed_at_version_one(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    message = Message(workspace_id=workspace.id, user_id=workspace.owner_id, body="Use SQLite")
    db_session.add(message)
    db_session.flush()
    item = SpecItem(
        workspace_id=workspace.id,
        kind=SpecItemKind.SUGGESTION,
        text="Use SQLite",
        source_message_ids=[message.id],
    )
    db_session.add(item)
    db_session.flush()
    db_session.refresh(item)

    assert item.status is SpecItemStatus.PROPOSED
    assert item.version == 1
    assert item.source_message_ids == [message.id]
    assert item.confirmed_by is None


def test_invalid_enum_value_is_rejected_by_orm(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    db_session.add(SpecItem(workspace_id=workspace.id, kind="opinion", text="x"))

    with pytest.raises(StatementError):
        db_session.flush()


def test_invalid_enum_value_is_rejected_by_database(db_session: Session) -> None:
    # Bypass the ORM entirely: the CHECK constraint itself must refuse unknown verdicts.
    run = make_run(db_session, make_workspace(db_session))

    with pytest.raises(IntegrityError):
        db_session.execute(
            text("INSERT INTO referee_runs (id, run_id, verdict) VALUES ('r1', :run, 'ok')"),
            {"run": run.id},
        )


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


def test_task_id_lists_default_empty(db_session: Session) -> None:
    task = make_task(db_session, make_workspace(db_session))
    db_session.refresh(task)

    assert task.status is TaskStatus.PROPOSED
    assert task.depends_on == []
    assert task.contract_ids == []


def test_knowledge_link_round_trip(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    task = make_task(db_session, workspace)
    db_session.add(
        KnowledgeLink(
            workspace_id=workspace.id,
            src_type=EntityType.REQUIREMENT,
            src_id="req-1",
            dst_type=EntityType.TASK,
            dst_id=task.id,
            relation="implemented_by",
        )
    )
    db_session.flush()

    link = db_session.scalars(select(KnowledgeLink).where(KnowledgeLink.src_id == "req-1")).one()
    assert link.dst_type is EntityType.TASK
    assert link.version == 1


def test_submission_and_check_result_defaults(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    submission = Submission(task_id=make_task(db_session, workspace).id, commit_sha="b" * 40)
    check = CheckResult(
        run_id=make_run(db_session, workspace).id, name="pytest", kind=CheckKind.LOCKED_TEST
    )
    db_session.add_all([submission, check])
    db_session.flush()
    db_session.refresh(submission)
    db_session.refresh(check)

    assert submission.status is SubmissionStatus.PENDING
    assert check.status is CheckStatus.PENDING
    assert check.exit_code is None
    assert check.artifacts_json == {}


def test_referee_run_defaults_to_not_run(db_session: Session) -> None:
    referee = RefereeRun(run_id=make_run(db_session, make_workspace(db_session)).id)
    db_session.add(referee)
    db_session.flush()
    db_session.refresh(referee)

    assert referee.verdict is RefereeVerdict.NOT_RUN
    assert referee.evidence_json == {}


def test_hidden_test_stores_location_and_starts_as_draft(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    hidden = HiddenTest(
        workspace_id=workspace.id, author_id=workspace.owner_id, location="/protected/qa_1.py"
    )
    db_session.add(hidden)
    db_session.flush()
    db_session.refresh(hidden)

    assert hidden.status is HiddenTestStatus.DRAFT
    assert hidden.approved_by is None


def test_credit_ledger_keeps_exact_amounts(db_session: Session) -> None:
    workspace = make_workspace(db_session)
    entry = CreditLedger(
        workspace_id=workspace.id,
        user_id=workspace.owner_id,
        kind=CreditKind.USAGE,
        amount_usd=Decimal("0.012345"),
        provider="claude",
        model="test-model",
    )
    db_session.add(entry)
    db_session.flush()
    db_session.expire(entry)

    assert entry.amount_usd == Decimal("0.012345")
    assert entry.kind is CreditKind.USAGE


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


def test_foreign_keys_are_enforced(db_session: Session) -> None:
    db_session.add(Message(workspace_id="missing", user_id="missing", body="orphan"))

    with pytest.raises(IntegrityError):
        db_session.flush()


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
