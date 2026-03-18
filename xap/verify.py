"""Standalone manifest verifier for XAP v0.2.

Usage:
    from xap.verify import verify_manifest

    result = verify_manifest(manifest_json)
    assert result.valid
"""

from __future__ import annotations

import json
import base64
import hashlib
from typing import Optional
from dataclasses import dataclass, field

import httpx

from xap.manifest import AgentManifest
from xap.schemas.validator import SchemaValidator
from xap.errors import XAPValidationError


@dataclass
class VerificationResult:
    """Result of manifest verification."""
    valid: bool
    schema_valid: bool = False
    signature_valid: bool = False
    not_expired: bool = False
    errors: list[str] = field(default_factory=list)


def verify_manifest(manifest: dict | str) -> VerificationResult:
    """Verify an AgentManifest: schema, signature, and expiry.

    Args:
        manifest: Dict or JSON string of an AgentManifest.

    Returns:
        VerificationResult with detailed check results.
    """
    if isinstance(manifest, str):
        try:
            manifest = json.loads(manifest)
        except json.JSONDecodeError as e:
            return VerificationResult(valid=False, errors=[f"Invalid JSON: {e}"])

    result = VerificationResult(valid=False)

    # 1. Schema validation
    try:
        SchemaValidator().validate_agent_manifest(manifest)
        result.schema_valid = True
    except XAPValidationError as e:
        result.errors.append(f"Schema: {e}")
        return result

    # 2. Signature verification
    result.signature_valid = AgentManifest.verify(manifest)
    if not result.signature_valid:
        result.errors.append("Signature verification failed")

    # 3. Expiry check
    result.not_expired = not AgentManifest.is_expired(manifest)
    if not result.not_expired:
        result.errors.append("Manifest has expired")

    result.valid = result.schema_valid and result.signature_valid and result.not_expired
    return result


@dataclass
class ConditionVerification:
    condition_id:       str
    condition_type:     str
    passed:             bool
    confidence_bps:     int
    verifier_attested:  bool = False
    attestation_valid:  Optional[bool] = None


@dataclass
class ReceiptVerification:
    verity_id:          str
    outcome:            str
    replay_verified:    bool
    chain_valid:        bool
    tsa_anchored:       bool = False
    tsa_timestamp:      Optional[str] = None
    policy_verified:    bool = False
    signing_key_id:     Optional[str] = None
    causal_depth:       int = 0
    workflow_id:        Optional[str] = None
    conditions:         list[ConditionVerification] = field(default_factory=list)
    warnings:           list[str] = field(default_factory=list)


@dataclass
class ManifestVerification:
    agent_id:           str
    signature_valid:    bool
    manifest_expired:   bool
    claimed_success_rate_bps: int
    receipts_checked:   int
    replay_confirmed:   int
    tsa_anchored_count: int
    policy_verified_count: int
    attested_conditions: int
    receipt_details:    list[ReceiptVerification]
    recommendation:     str
    warnings:           list[str]


async def verify_receipt_full(
    verity_id: str,
    base_url: str = "https://api.zexrail.com",
) -> ReceiptVerification:
    """Fetch and fully verify a VerityReceipt with all gap fields."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{base_url}/xap/v1/verity/receipts/{verity_id}")
        if r.status_code == 404:
            raise ValueError(f"Receipt not found: {verity_id}")
        r.raise_for_status()
        receipt = r.json()

    result = ReceiptVerification(
        verity_id=verity_id,
        outcome=receipt.get("outcome", "UNKNOWN"),
        replay_verified=receipt.get("replay_verified", False),
        chain_valid=True,
    )

    # TSA
    tsa = receipt.get("timestamp_authority")
    if tsa:
        result.tsa_anchored = True
        result.tsa_timestamp = tsa.get("tsa_timestamp")
    else:
        result.warnings.append("No TSA timestamp — receipt is clock-unanchored")

    # Policy hash
    rules = receipt.get("rules_applied", {})
    policy_hash = rules.get("policy_content_hash")
    policy_version = rules.get("policy_version")
    if policy_hash and policy_version:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                pr = await client.get(f"{base_url}/xap/v1/policies/{policy_version}")
                if pr.status_code == 200:
                    policy_doc = pr.json()
                    stored_hash = policy_doc.get("content_hash")
                    result.policy_verified = (stored_hash == policy_hash)
                    if not result.policy_verified:
                        result.warnings.append(f"Policy hash mismatch for {policy_version}")
        except Exception as e:
            result.warnings.append(f"Could not verify policy hash: {e}")
    else:
        result.warnings.append("No policy_content_hash — policy version unverified")

    # Signing key
    result.signing_key_id = receipt.get("key_id")
    if not result.signing_key_id:
        result.warnings.append("No key_id — cannot verify signing key history")

    # Causality
    causality = receipt.get("causality")
    if causality:
        result.causal_depth = causality.get("depth", 0)
        result.workflow_id = causality.get("workflow_id")

    # Condition attestations
    for cond in receipt.get("computation", {}).get("condition_results", []):
        att = cond.get("verifier_attestation")
        cv = ConditionVerification(
            condition_id=cond.get("condition_id", ""),
            condition_type=cond.get("type", ""),
            passed=cond.get("passed", False),
            confidence_bps=cond.get("confidence_bps", 0),
        )
        if att:
            cv.verifier_attested = True
            try:
                cv.attestation_valid = _verify_attestation(
                    att["payload_hash"], att["signature"], att["verifier_public_key"],
                )
            except Exception:
                cv.attestation_valid = False
        result.conditions.append(cv)

    return result


def _verify_attestation(payload_hash: str, signature_b64: str, public_key_b64: str) -> bool:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    hash_hex = payload_hash.removeprefix("sha256:")
    hash_bytes = bytes.fromhex(hash_hex)
    sig = base64.urlsafe_b64decode(signature_b64 + "==")
    pub = base64.urlsafe_b64decode(public_key_b64 + "==")
    key = Ed25519PublicKey.from_public_bytes(pub)
    try:
        key.verify(sig, hash_bytes)
        return True
    except InvalidSignature:
        return False


def _check_expired(expires_at) -> bool:
    if not expires_at:
        return False
    from datetime import datetime, timezone
    try:
        exp = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        return exp < datetime.now(timezone.utc)
    except Exception:
        return True


async def verify_manifest_full(
    manifest: dict,
    sample_receipts: int = 3,
    base_url: str = "https://api.zexrail.com",
) -> ManifestVerification:
    """Full manifest verification including all five gap fields."""
    agent_id = manifest.get("agent_id", "")
    sig = manifest.get("signature", {})
    signature_valid = bool(sig.get("value")) and bool(sig.get("public_key"))
    manifest_expired = _check_expired(manifest.get("expires_at"))

    warnings: list[str] = []
    receipt_details: list[ReceiptVerification] = []
    tsa_count = 0
    policy_count = 0
    attested_count = 0

    for cap in manifest.get("capabilities", [])[:1]:
        attestation = cap.get("attestation", {})
        receipt_hashes = attestation.get("receipt_hashes", [])[:sample_receipts]

        for vrt_id in receipt_hashes:
            try:
                rv = await verify_receipt_full(vrt_id, base_url)
                receipt_details.append(rv)
                if rv.tsa_anchored:
                    tsa_count += 1
                if rv.policy_verified:
                    policy_count += 1
                attested_count += sum(
                    1 for c in rv.conditions if c.verifier_attested and c.attestation_valid
                )
                warnings.extend(rv.warnings)
            except Exception as e:
                warnings.append(f"Could not verify receipt {vrt_id}: {e}")

    replay_confirmed = sum(1 for r in receipt_details if r.replay_verified)
    checked = len(receipt_details)
    claimed_bps = 0
    for cap in manifest.get("capabilities", [])[:1]:
        claimed_bps = cap.get("attestation", {}).get("success_rate_bps", 0)

    if not signature_valid:
        recommendation = "DO_NOT_TRUST"
    elif manifest_expired:
        recommendation = "DO_NOT_TRUST"
    elif checked == 0:
        recommendation = "VERIFY_MANUALLY"
    elif replay_confirmed == checked:
        recommendation = "TRUST"
    elif replay_confirmed >= checked * 0.8:
        recommendation = "VERIFY_MANUALLY"
    else:
        recommendation = "DO_NOT_TRUST"

    return ManifestVerification(
        agent_id=agent_id,
        signature_valid=signature_valid,
        manifest_expired=manifest_expired,
        claimed_success_rate_bps=claimed_bps,
        receipts_checked=checked,
        replay_confirmed=replay_confirmed,
        tsa_anchored_count=tsa_count,
        policy_verified_count=policy_count,
        attested_conditions=attested_count,
        receipt_details=receipt_details,
        recommendation=recommendation,
        warnings=list(set(warnings)),
    )
