"""Domain enums, stored as their lowercase values with CHECK constraints."""

from enum import StrEnum


class MemberRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"


class VerificationProfile(StrEnum):
    FAST = "fast"
    STANDARD = "standard"
    STRICT = "strict"


class SpecItemKind(StrEnum):
    REQUIREMENT = "requirement"
    DECISION = "decision"
    SUGGESTION = "suggestion"
    QUESTION = "question"


class SpecItemStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ContractKind(StrEnum):
    API = "api"
    SCHEMA = "schema"
    TYPE = "type"


class ContractStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class TaskStatus(StrEnum):
    PROPOSED = "proposed"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    FAILED = "failed"
    DONE = "done"


class EntityType(StrEnum):
    """Node types in the knowledge store (ARCHITECTURE section 8)."""

    REQUIREMENT = "requirement"
    DECISION = "decision"
    CONTRACT = "contract"
    TASK = "task"
    SUBMISSION = "submission"
    COMMIT = "commit"
    CHECK_RESULT = "check_result"
    FAILURE = "failure"


class SubmissionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"


class CheckKind(StrEnum):
    MERGE = "merge"
    BUILD = "build"
    LOCKED_TEST = "locked_test"
    HIDDEN_TEST = "hidden_test"
    LINT = "lint"
    CONTRACT = "contract"
    DEPENDENCY_SCAN = "dependency_scan"
    SECRET_SCAN = "secret_scan"  # noqa: S105 - check name, not a credential


class CheckStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class HiddenTestStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


class RefereeVerdict(StrEnum):
    """TRD R11. Only PASS counts as a pass; every other verdict is non-passing."""

    PASS = "pass"  # noqa: S105 - verdict name, not a credential
    APP_FAILURE = "app_failure"
    BROWSER_FAILURE = "browser_failure"
    SERVICE_ERROR = "service_error"
    INCONCLUSIVE = "inconclusive"
    NOT_RUN = "not_run"


class FailureStatus(StrEnum):
    OPEN = "open"
    ROUTED = "routed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class CreditKind(StrEnum):
    PORTION = "portion"
    USAGE = "usage"
    LOAN = "loan"
    HOUSE = "house"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
