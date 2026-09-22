"""Nexivra AI — evidence-first autonomous research and agent platform.

Core pipeline: ASK -> PLAN -> RESEARCH -> COLLECT EVIDENCE -> CROSS-CHECK
-> VERIFY -> SYNTHESIZE -> ACT.

Proprietary code (see LICENSE). Third-party components remain under their
own licenses; see THIRD-PARTY-NOTICES.md.
"""

from .types import ClaimStatus, SourceTier
from .evidence import SourceRegistry, EvidenceStore
from .claims import ClaimRegistry
from .conflicts import ContradictionDetector, ConflictReport
from .verify import VerificationEngine, VerificationReport
from .gateway import UniversalModelGateway
from .vault import ProviderVault
from .quotas import QuotaGovernor, BudgetExhausted
from .audit import AuditLogger
from .memory import ResearchMemory
from .research import ResearchEngine, ResearchMode, RunLimits
from .ssrf import assert_safe_url, UnsafeUrlError
from .local import (
    APIAwareRouter,
    DeviceProfile,
    FailureKind,
    LocalModelSpec,
    LocalModelUnavailable,
    QWEN3_06B,
    SMOLLM2_135M,
    StubLocalRuntime,
    classify_failure,
)

__version__ = "0.2.0"

__all__ = [
    "ClaimStatus",
    "SourceTier",
    "SourceRegistry",
    "EvidenceStore",
    "ClaimRegistry",
    "ContradictionDetector",
    "ConflictReport",
    "VerificationEngine",
    "VerificationReport",
    "UniversalModelGateway",
    "ProviderVault",
    "QuotaGovernor",
    "BudgetExhausted",
    "AuditLogger",
    "ResearchMemory",
    "ResearchEngine",
    "ResearchMode",
    "RunLimits",
    "assert_safe_url",
    "UnsafeUrlError",
    "APIAwareRouter",
    "DeviceProfile",
    "FailureKind",
    "LocalModelSpec",
    "LocalModelUnavailable",
    "QWEN3_06B",
    "SMOLLM2_135M",
    "StubLocalRuntime",
    "classify_failure",
    "__version__",
]
