# PROOF Security Policy

## Reporting Vulnerabilities

**DO NOT** open public issues for security bugs.

| Severity | Contact | Response time |
|----------|---------|---------------|
| Critical (false VERIFIED verdict) | anna.tchijova@icloud.com | 4 hours |
| High (evidence tamper bypass) | anna.tchijova@icloud.com | 24 hours |
| Medium/Low | GitHub Issues | 7 days |

Include the commit hash, the input that triggers the issue, and the
observed vs. expected output.

## Threat Model

### What PROOF protects against

- **Screenshot fraud:** a fake screenshot claiming payment.
- **Claim mismatch:** a real transaction that does not match the claimed
  terms (sender, recipient, asset, amount, reference).
- **Evidence tampering:** modifying the evidence bundle after sealing.
  The verifier recomputes SHA-256 over the canonical payload; any
  modification breaks the seal.
- **Commitment fraud:** claiming a payment matches a commitment when it
  does not. The commitment hash is `SHA-256(canonical(CommitmentTerms))`;
  a mismatch produces NOT_VERIFIED.

### What PROOF does NOT protect against

- **Compromised Horizon server:** false ledger data from a
  man-in-the-middle. PROOF is only as trustworthy as its Horizon
  connection. There is no TLS certificate pinning (Finding 3, red-team
  review).
- **Network failures:** transient errors produce INSUFFICIENT_EVIDENCE,
  not an error. This is fail-closed but can mislead users into thinking
  a transaction does not exist when the network is down.
- **Legal disputes:** PROOF does not adjudicate contractual
  obligations. A VERIFIED verdict means the ledger shows a matching
  payment — not that a debt was legally satisfied.
- **Identity:** a wallet signature does not prove human identity.

### What PROOF cannot verify

- That goods or services were delivered.
- That a debt was legally satisfied.
- That the person controlling a wallet is a specific human.
- That the committed terms are true (only that they were committed).

## Architecture

### Deterministic core

The verdict decision path is deterministic and sealed before any
narrative layer runs:

- No float in the decision path. Amounts are integer stroops. The
  canonicalizer rejects unexpected types (Finding 5, fixed).
- SHA-256 over canonical, type-tagged, key-sorted, versioned
  serialization. One canonical encoder used everywhere.
- Three-state verdicts: VERIFIED, NOT_VERIFIED, INSUFFICIENT_EVIDENCE.
  ABSTAIN is a valid check status for unspecified fields.
- Fail-closed: no error path returns VERIFIED.

### Boundary validation

All untrusted inputs are validated at the boundary:

- `PaymentClaim.__post_init__` validates transaction hash (64-char hex),
  account keys (G...), asset codes, stroop amounts (integer, non-bool).
- `amount_to_stroops` rejects fractional stroops (Finding 1, fixed).
- `canonicalize` raises `TypeError` on unexpected types (Finding 5,
  fixed).
- `fetch_transaction` distinguishes "not found" from "network error"
  (Finding 2, fixed).

### Soroban contract

The on-chain registry enforces:

- `require_auth()` on both commitment and receipt registration. Only
  the committer account can register.
- Immutability: panic on overwrite. A commitment or receipt, once
  registered, cannot be modified.
- Temporal order: `verify_temporal_order` uses strict `<`, not `<=`.

The contract stores pre-computed hashes. It does not canonicalize or
verify terms — that is the off-chain core's job. The contract is a
registry, not a verifier.

### Public deployment

The public API on Cloud Run:

- Exposes read-only endpoints publicly: health, verify, on-chain
  commitment/receipt retrieval.
- Blocks write endpoints (`/commit`, `/onchain/register-receipt`) by
  using a valid but unfunded Testnet identity. Writes fail naturally
  with "Account not found" — no protocol shortcut, no funded demo
  identity.
- Does not authenticate callers. This is a known limitation, not a
  feature.

## Known limitations

These are documented as open, not as resolved:

- **No rate limiting:** the public API has no rate limiting. A
  determined attacker could flood the API and cause Horizon rate
  limiting.
- **No TLS pinning to Horizon:** the Stellar SDK uses system CAs. A
  compromised CA or MITM with a valid certificate could feed false data.
- **No caller authentication:** the public API is open. Deploy behind a
  gateway with auth/rate-limiting for production.
- **Cloud Run cold starts:** the first request after idle may take
  1-2 seconds.
- **Testnet transaction pruning:** Stellar may prune old Testnet
  transactions. The reproducible evidence in this README may
  eventually become unavailable from Horizon.

## Red-team review

A full red-team review was conducted on 2026-09-22. The review found
no critical vulnerabilities that would allow a false VERIFIED verdict.
7 findings were reported; 6 code findings were fixed, 1 (API auth) is
documented as a known limitation.

See [`docs/red-team-review.md`](docs/red-team-review.md) for the full
report.

## Audit history

| Date | Auditor | Result |
|------|---------|--------|
| 2026-09-22 | Adversarial red-team review | 7 findings (6 fixed, 1 documented) |
