"""SQLAlchemy models. Importing this package registers every table on `Base.metadata`."""

from app.models.approval import Approval
from app.models.base import Base
from app.models.contract import Contract
from app.models.credit import CreditLedger
from app.models.hidden_test import HiddenTest
from app.models.integration import CheckResult, Failure, IntegrationRun
from app.models.invite import Invite
from app.models.job import Job
from app.models.knowledge import KnowledgeLink
from app.models.message import Message
from app.models.referee import RefereeRun
from app.models.spec import SpecItem, SpecVersion
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Member, Workspace

__all__ = [
    "Approval",
    "Base",
    "CheckResult",
    "Contract",
    "CreditLedger",
    "Failure",
    "HiddenTest",
    "IntegrationRun",
    "Invite",
    "Job",
    "KnowledgeLink",
    "Member",
    "Message",
    "RefereeRun",
    "SpecItem",
    "SpecVersion",
    "Submission",
    "Task",
    "User",
    "Workspace",
]
