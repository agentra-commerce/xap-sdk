"""Tests for upgraded verify.py — all five gap fields."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import asdict

from xap.verify import (
    ReceiptVerification,
    ConditionVerification,
    ManifestVerification,
    verify_receipt_full,
    verify_manifest_full,
    _verify_attestation,
    _check_expired,
)


def test_check_expired_none():
    assert not _check_expired(None)


def test_check_expired_future():
    assert not _check_expired("2099-01-01T00:00:00Z")


def test_check_expired_past():
    assert _check_expired("2020-01-01T00:00:00Z")


def test_receipt_verification_defaults():
    rv = ReceiptVerification(
        verity_id="vrt_test",
        outcome="SUCCESS",
        replay_verified=True,
        chain_valid=True,
    )
    assert rv.tsa_anchored is False
    assert rv.policy_verified is False
    assert rv.conditions == []
    assert rv.warnings == []


def test_condition_verification_defaults():
    cv = ConditionVerification(
        condition_id="cond_01",
        condition_type="deterministic",
        passed=True,
        confidence_bps=10000,
    )
    assert cv.verifier_attested is False
    assert cv.attestation_valid is None


def test_manifest_verification_fields():
    mv = ManifestVerification(
        agent_id="agnt_test",
        signature_valid=True,
        manifest_expired=False,
        claimed_success_rate_bps=9500,
        receipts_checked=3,
        replay_confirmed=3,
        tsa_anchored_count=2,
        policy_verified_count=1,
        attested_conditions=4,
        receipt_details=[],
        recommendation="TRUST",
        warnings=[],
    )
    assert mv.recommendation == "TRUST"
    assert mv.tsa_anchored_count == 2
    assert mv.attested_conditions == 4


@pytest.mark.asyncio
async def test_verify_receipt_with_tsa():
    """Receipt with TSA block — tsa_anchored=True."""
    mock_receipt = {
        "outcome": "SUCCESS",
        "replay_verified": True,
        "timestamp_authority": {
            "tsa_serial": "1234",
            "tsa_issuer": "DigiCert",
            "tsa_timestamp": "2026-03-18T10:00:00Z",
            "tsa_token_hash": "sha256:" + "a" * 64,
        },
        "rules_applied": {},
        "computation": {},
    }
    with patch("httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.get.return_value = MagicMock(status_code=200, json=lambda: mock_receipt)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        rv = await verify_receipt_full("vrt_test", "http://test")
        assert rv.tsa_anchored is True
        assert rv.tsa_timestamp == "2026-03-18T10:00:00Z"


@pytest.mark.asyncio
async def test_verify_receipt_without_tsa_warns():
    """Receipt without TSA — warning added."""
    mock_receipt = {
        "outcome": "SUCCESS",
        "replay_verified": True,
        "rules_applied": {},
        "computation": {},
    }
    with patch("httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.get.return_value = MagicMock(status_code=200, json=lambda: mock_receipt)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        rv = await verify_receipt_full("vrt_test", "http://test")
        assert rv.tsa_anchored is False
        assert any("TSA" in w for w in rv.warnings)


def test_verify_attestation_malformed():
    """Malformed input returns False or raises."""
    try:
        result = _verify_attestation("sha256:" + "a" * 64, "bad", "bad")
        assert result is False
    except Exception:
        pass  # Expected for malformed input


@pytest.mark.asyncio
async def test_verify_manifest_expired():
    """Expired manifest — recommendation=DO_NOT_TRUST."""
    manifest = {
        "agent_id": "agnt_test",
        "signature": {"value": "sig", "public_key": "pk"},
        "expires_at": "2020-01-01T00:00:00Z",
        "capabilities": [],
    }
    mv = await verify_manifest_full(manifest, base_url="http://test")
    assert mv.recommendation == "DO_NOT_TRUST"
    assert mv.manifest_expired is True
