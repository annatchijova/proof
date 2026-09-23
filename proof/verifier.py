"""
verifier.py — Independent, stdlib-only verifier for evidence bundles.

This module does NOT import any PROOF code except canonicalize. It recomputes
the SHA-256 seal from the bundle's sealed payload and confirms it matches.
A verifier that imports the producer's logic can inherit the producer's bug,
so this is deliberately independent.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .canonicalize import canonicalize


def verify_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Verify an evidence bundle's seal.

    Returns a report with:
      - seal_ok: True if the recomputed seal matches the stored seal.
      - version_ok: True if the bundle version matches the canonicalizer version.
      - verdict_consistent: True if the verdict is consistent with the checks.
      - issues: list of any problems found.
    """
    issues: list[str] = []

    # Extract the sealed payload fields.
    sealed_payload: dict[str, Any] = {
        "version": bundle.get("version"),
        "claim": bundle.get("claim"),
        "evidence": bundle.get("evidence"),
        "checks": bundle.get("checks"),
        "verdict": bundle.get("verdict"),
        "scope_notes": bundle.get("scope_notes"),
    }
    # L4: commitment is optional. Include it only if present, matching
    # the producer's behavior (the seal covers commitment only when set).
    commitment = bundle.get("commitment")
    if commitment is not None:
        sealed_payload["commitment"] = commitment

    stored_seal = bundle.get("seal")
    if not isinstance(stored_seal, str):
        issues.append("seal field is missing or not a string")
        return {"seal_ok": False, "version_ok": False, "verdict_consistent": False, "issues": issues}

    # Recompute the seal.
    canon = canonicalize(sealed_payload)
    recomputed = hashlib.sha256(
        json.dumps(canon, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    seal_ok = recomputed == stored_seal
    if not seal_ok:
        issues.append(f"seal mismatch: stored={stored_seal}, recomputed={recomputed}")

    # Check version.
    from .canonicalize import CANONICALIZE_VERSION
    version_ok = bundle.get("version") == CANONICALIZE_VERSION
    if not version_ok:
        issues.append(
            f"version mismatch: bundle={bundle.get('version')}, "
            f"expected={CANONICALIZE_VERSION}"
        )

    # Check verdict consistency against the three-state contract.
    checks = bundle.get("checks", [])
    has_fail = any(c.get("status") == "FAIL" for c in checks)
    verdict = bundle.get("verdict", "")
    verdict_consistent = True
    allowed_verdicts = {"VERIFIED", "NOT_VERIFIED", "INSUFFICIENT_EVIDENCE"}
    if verdict not in allowed_verdicts:
        verdict_consistent = False
        issues.append(f"unknown verdict: {verdict!r}")
    elif has_fail and verdict == "VERIFIED":
        verdict_consistent = False
        issues.append(
            "verdict inconsistent: checks contain FAIL but verdict is VERIFIED"
        )
    elif not has_fail and verdict in ("NOT_VERIFIED", "INSUFFICIENT_EVIDENCE"):
        verdict_consistent = False
        issues.append(
            f"verdict inconsistent: no FAIL in checks but verdict is {verdict!r}"
        )

    return {
        "seal_ok": seal_ok,
        "version_ok": version_ok,
        "verdict_consistent": verdict_consistent,
        "issues": issues,
    }
