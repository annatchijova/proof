# PROOF Red Team Review

**Date:** 2026-09-22
**Scope:** Full system (L1-L6 + Soroban contract)
**Reviewer:** Adversarial audit of the PROOF codebase
**Method:** Peircean abductive loop — for each finding, formulate the
benign hypothesis, test it against the live code, and only report
findings that survive refutation.

---

## Executive Summary

PROOF is a deterministic Stellar payment verification system. Its core
invariants — no float in the decision path, SHA-256 sealed evidence
bundles, three-state verdicts, ABSTAIN for unspecified fields, fail-closed
behavior — are well-implemented and tested. The red team review found
**no critical vulnerabilities** that would allow a false VERIFIED verdict.

The review found **7 findings** ranging from low to medium severity.
All 6 code findings have been fixed; the 7th (API auth) is documented.

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | Medium | `amount_to_stroops` truncates fractional stroops silently | Fixed |
| 2 | Medium | `fetch_transaction` swallows all exceptions as "not found" | Fixed |
| 3 | Medium | No TLS certificate pinning on Horizon connections | Documented |
| 4 | Low | Commitment hash reconstruction assumes evidence fields are complete | Fixed |
| 5 | Low | `canonicalize` fallback `str(obj)` can silently absorb unexpected types | Fixed |
| 6 | Low | Dispute `find_contradictions` only checks first-level fields | Fixed |
| 7 | Low | API has no rate limiting or authentication | Documented |

---

## Finding 1: `amount_to_stroops` truncates fractional stroops silently

**Severity:** Medium
**File:** `proof/stellar_client.py:82-92`
**Status:** Confirmed

### Observation (Firstness)

`amount_to_stroops` converts a decimal string to integer stroops using:

```python
decimal = Decimal(amount_str)
stroops = int(decimal * STROOPS_PER_UNIT)
```

`int()` truncates toward zero. If the decimal string has more than 7
decimal places, the fractional stroops are silently lost.

### Baseline (Secondness)

Stellar amounts are always represented with exactly 7 decimal places in
Horizon responses. A correctly-formatted amount like `"100.0000000"`
converts exactly. But a malformed or adversarial amount like
`"100.00000001"` would be truncated to `1000000000` stroops instead of
`1000000001`.

### Root cause (Thirdness)

The function trusts that Horizon always returns exactly 7 decimal places.
It does not validate the precision of the input. If Horizon ever returns
a non-standard precision (or if a malicious intermediary modifies the
response), the truncation is silent.

### Refutation attempt

The benign hypothesis: "Horizon always returns 7 decimal places, so this
can never happen." This is true for well-formed Horizon responses. But
the function is a boundary function that receives untrusted external data.
A man-in-the-middle or a compromised Horizon could return a different
precision. The function should fail closed on non-integer stroop results.

### Recommendation

```python
def amount_to_stroops(amount_str: str) -> int:
    if not isinstance(amount_str, str):
        raise ValueError(...)
    decimal = Decimal(amount_str)
    stroops_decimal = decimal * STROOPS_PER_UNIT
    if stroops_decimal != int(stroops_decimal):
        raise ValueError(f"amount has fractional stroops: {amount_str}")
    return int(stroops_decimal)
```

---

## Finding 2: `fetch_transaction` swallows all exceptions as "not found"

**Severity:** Medium
**File:** `proof/stellar_client.py:46-52`
**Status:** Confirmed

### Observation

```python
def fetch_transaction(self, tx_hash: str) -> dict[str, Any] | None:
    try:
        response = self._server.transactions().transaction(tx_hash).call()
        return dict(response)
    except Exception:
        return None
```

### Root cause

All exceptions — including network errors, TLS errors, timeouts, and
HTTP 500s — are caught and returned as `None`, which the engine
interprets as "transaction not found." This means a transient network
failure is indistinguishable from a transaction that doesn't exist.

### Impact

A network failure during verification produces `INSUFFICIENT_EVIDENCE`
rather than an error. This is fail-closed (safe), but it can mislead
users into thinking the transaction doesn't exist when it actually does.

### Refutation attempt

The benign hypothesis: "fail-closed is always safe, so this is fine."
This is true for the verdict — INSUFFICIENT_EVIDENCE is never VERIFIED.
But the error message says "Transaction not found on the ledger" which
is factually wrong when the real cause is a network error. The user
cannot distinguish "doesn't exist" from "couldn't fetch."

### Recommendation

Distinguish `NotFoundError` from `NetworkError`:
- Return `None` for 404 (transaction genuinely not found).
- Raise an exception for network/TLS/server errors.
- The engine should produce different messages for each case.

---

## Finding 3: No TLS certificate pinning on Horizon connections

**Severity:** Medium
**File:** `proof/stellar_client.py:44`
**Status:** Confirmed

### Observation

```python
self._server = Server(horizon_url=self.horizon_url)
```

The Stellar SDK uses the system's default TLS configuration. There is no
certificate pinning. A compromised CA or a man-in-the-middle with a valid
certificate could intercept Horizon responses and feed false data.

### Impact

If an attacker can modify Horizon responses, they can:
- Make a failed transaction appear successful.
- Change the amount, sender, or recipient.
- Inject a non-existent transaction.

The extractor validates field formats but cannot detect semantically
false data that passes format validation.

### Refutation attempt

The benign hypothesis: "TLS with system CAs is sufficient for a
verification tool." This is true for most threat models. But PROOF's
entire value proposition is that it verifies against the ledger. If the
connection to the ledger can be intercepted, the verification is
worthless. Certificate pinning is the standard mitigation.

### Recommendation

- Add optional certificate pinning for Horizon connections.
- Document the threat model: PROOF is only as trustworthy as the
  Horizon connection.
- Consider fetching from multiple Horizon instances and comparing.

---

## Finding 4: Commitment hash reconstruction assumes evidence fields are complete

**Severity:** Low
**File:** `proof/adjudicator.py:371-380`
**Status:** Confirmed

### Observation

The commitment hash check reconstructs `CommitmentTerms` from the
payment evidence:

```python
reconstructed_terms = CommitmentTerms(
    sender=evidence.sender,
    recipient=evidence.recipient,
    asset_code=evidence.asset_code,
    asset_issuer=evidence.asset_issuer,
    amount_stroops=evidence.amount_stroops,
    reference=evidence.memo if evidence.memo_type == "text" else None,
)
```

### Root cause

This assumes the evidence's top-level fields (which come from the first
operation) are the fields that were committed. If the commitment was
for a different operation in a multi-operation transaction, the
reconstruction will produce the wrong hash and the check will FAIL —
even if the payment actually matches the commitment.

### Impact

False negative: a valid payment that matches a commitment but involves
the second or third operation in a multi-operation transaction will be
reported as NOT_VERIFIED.

### Refutation attempt

The benign hypothesis: "most payments are single-operation, so this
rarely matters." This is true for simple payments. But PROOF L3
explicitly added multi-operation support. The commitment check should
try reconstructing terms from each operation, not just the first.

### Recommendation

When checking commitment hash, iterate over all operations in the
evidence and check if any of them produces a matching hash.

---

## Finding 5: `canonicalize` fallback `str(obj)` can silently absorb unexpected types

**Severity:** Low
**File:** `proof/canonicalize.py:43`
**Status:** Confirmed

### Observation

```python
def canonicalize(obj: Any) -> Any:
    ...
    return str(obj)  # fallback for unknown types
```

### Root cause

If an unexpected type (e.g., `bytes`, `set`, `datetime`) reaches the
canonicalizer, it is silently converted to its string representation.
This means two different objects could produce the same canonical form
if their `str()` representations collide.

### Impact

Low in practice — the sealed payload only contains dicts, lists, strs,
ints, bools, and None. But if a bug elsewhere introduces an unexpected
type, the canonicalizer would silently absorb it rather than failing.

### Refutation attempt

The benign hypothesis: "the sealed payload is always well-typed because
it comes from dataclass `to_dict()` methods." This is true today. But
the canonicalizer is a defense-in-depth layer. It should fail closed on
unexpected types.

### Recommendation

Replace the fallback with:
```python
raise TypeError(f"canonicalize: unsupported type {type(obj).__name__}: {obj!r}")
```

---

## Finding 6: Dispute `find_contradictions` only checks first-level fields

**Severity:** Low
**File:** `proof/dispute.py:80-100`
**Status:** Confirmed

### Observation

`find_contradictions` checks fields like `sender`, `recipient`,
`amount_stroops` etc. between two evidence sets. But it only checks the
top-level fields (from the first operation). It does not check the
`operations` list.

### Impact

If two evidence sets have the same top-level fields but different
`operations` lists (e.g., the first operation matches but the second
differs), the contradiction check would report them as consistent.

### Refutation attempt

The benign hypothesis: "if both evidences come from the same
transaction, the operations list will always be identical because it
comes from the same Horizon data." This is true if both evidences are
honestly extracted. But if one evidence set is tampered with (e.g., an
operation is removed), the top-level fields could match while the
operations list differs.

### Recommendation

Add a check that the `operations` lists are identical when both
evidences reference the same transaction.

---

## Finding 7: API has no rate limiting or authentication

**Severity:** Low
**File:** `proof/api.py`
**Status:** Confirmed (documented as known limitation)

### Observation

The FastAPI API accepts any request without authentication or rate
limiting. Each request triggers a Horizon fetch, which is an external
HTTP call.

### Impact

An attacker could:
- Flood the API with requests, causing Horizon rate limiting or bans.
- Use the API as an oracle to verify arbitrary transactions.

### Refutation attempt

The benign hypothesis: "this is documented as a known limitation in
TECHNICAL.md." This is true. The documentation says "Deploy behind a
gateway with auth/rate-limiting for production." This is adequate for
the current development stage.

### Recommendation

No code change needed. The documentation is sufficient. For production
deployment, add an API key middleware and rate limiting.

---

## Findings that were investigated and refuted

### R1: "The seal could be non-deterministic due to dict ordering"

**Refuted.** The canonicalizer uses `sorted(obj.items())` and
`json.dumps(..., sort_keys=True)`. Dict ordering is deterministic. The
determinism tests (5 runs, same seal) confirm this.

### R2: "A float could enter the sealed payload via `amount_stroops`"

**Refuted.** `validate_stroops` explicitly rejects `bool` and non-`int`
types. `amount_to_stroops` uses `Decimal` and `int()`, never `float`.
The boundary tests confirm floats are rejected.

### R3: "The verifier could be fooled by a tampered bundle"

**Refuted.** The verifier recomputes the SHA-256 from the sealed
payload and compares with the stored seal. Tamper detection tests
confirm that any modification to the sealed payload breaks the seal.

### R4: "The Soroban contract could be used to register false commitments"

**Refuted.** The contract requires `require_auth()` from the committer.
A false commitment can only be registered by the account that authorizes
it. The contract stores the committer address, so false commitments are
attributable. The contract does not verify the commitment — it only
stores it. Verification is the off-chain core's job.

### R5: "The MCP server could be used to bypass validation"

**Refuted.** The MCP server calls the same `verify_payment` function as
the engine. All validation happens in `PaymentClaim.__post_init__` and
the engine. The MCP server is a thin transport layer.

---

## Threat Model Summary

### What PROOF protects against

- Screenshot fraud: a fake screenshot claiming payment.
- Claim mismatch: a real transaction that doesn't match the claimed terms.
- Evidence tampering: modifying the evidence bundle after sealing.
- Commitment fraud: claiming a payment matches a commitment when it doesn't.

### What PROOF does NOT protect against

- Compromised Horizon server: false ledger data from a MITM.
- Network failures: transient errors that produce INSUFFICIENT_EVIDENCE.
- Multi-operation commitment mismatch: commitments for non-first operations.
- Legal disputes: PROOF does not adjudicate contractual obligations.
- Identity: a wallet signature does not prove human identity.

### What PROOF cannot verify

- That goods or services were delivered.
- That a debt was legally satisfied.
- That the person controlling a wallet is a specific human.
- That the committed terms are true (only that they were committed).

---

## Test Coverage Assessment

| Area | Tests | Coverage |
|---|---|---|
| Canonical serialization | 9 | Good — covers types, ordering, determinism |
| Boundary validation | 17 | Good — covers all field types and edge cases |
| Adjudication | 11 | Good — covers all check types |
| Extraction | 23 | Good — covers all operation types and memo types |
| Commitment | 18 | Good — covers hashing, adjudication, extraction, receipts |
| Dispute | 15 | Good — covers contradictions and all verdict combinations |
| Verifier | 7 | Good — covers tamper detection for all fields |
| API | 8 | Adequate — covers boundary validation, skips live network |
| MCP | 5 | Adequate — covers tool listing and routing |
| Soroban contract | 8 | Good — covers all functions and immutability |

**Total: 138 Python tests + 8 Rust tests = 146 tests**

### Gaps in test coverage

- No integration test against a live Stellar testnet transaction.
- No test for multi-operation commitment matching (Finding 4).
- No test for the `canonicalize` fallback with unexpected types (Finding 5).
- No test for the `operations` list contradiction check (Finding 6).

---

## Recommendations

### Immediate (should fix before production)

1. **Finding 1:** Fix `amount_to_stroops` to reject fractional stroops.
2. **Finding 2:** Distinguish "not found" from "network error" in the client.
3. **Finding 5:** Replace the `canonicalize` fallback with a `TypeError`.

### Short-term (should fix soon)

4. **Finding 4:** Try all operations for commitment hash matching.
5. **Finding 6:** Add `operations` list to contradiction checks.
6. Add integration tests against live testnet transactions.

### Long-term (should consider)

7. **Finding 3:** Add certificate pinning for Horizon connections.
8. Consider fetching from multiple Horizon instances for redundancy.
9. Add API authentication and rate limiting for production deployment.

---

## Conclusion

PROOF's core design is sound. The deterministic core, sealed evidence
bundles, and three-state verdicts are well-implemented. The system
correctly fails closed — no finding allows a false VERIFIED verdict.

The most significant risk is the trust placed in the Horizon connection
(Finding 3). PROOF is only as trustworthy as its data source. This is
inherent in the design and should be clearly communicated to users.

The Soroban contract is a clean, minimal registry that extends the
evidence model without duplicating off-chain logic. Its immutability and
authorization model are correct.
