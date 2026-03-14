"""XAP Protocol SDK — Settlement objects for autonomous agent commerce."""

__version__ = "0.4.0"

from xap.types import (
    Money,
    Currency,
    BasisPoints,
    validate_shares,
    AgentId,
    SettlementId,
    ReceiptId,
    VerityId,
    ContractId,
    QueryId,
    CanonicalTimestamp,
)
from xap.errors import (
    XAPError,
    XAPValidationError,
    XAPCryptoError,
    XAPStateError,
    XAPAdapterError,
    XAPBuilderError,
)
from xap.crypto import (
    canonical_serialize,
    canonical_hash,
    compute_replay_hash,
    XAPSigner,
)
from xap.client import XAPClient

__all__ = [
    "__version__",
    "Money",
    "Currency",
    "BasisPoints",
    "validate_shares",
    "AgentId",
    "SettlementId",
    "ReceiptId",
    "VerityId",
    "ContractId",
    "QueryId",
    "CanonicalTimestamp",
    "XAPError",
    "XAPValidationError",
    "XAPCryptoError",
    "XAPStateError",
    "XAPAdapterError",
    "XAPBuilderError",
    "canonical_serialize",
    "canonical_hash",
    "compute_replay_hash",
    "XAPSigner",
    "XAPClient",
]
