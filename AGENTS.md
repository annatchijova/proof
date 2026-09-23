# AGENTS.md — Engineering Discipline for PROOF

## What this is

PROOF verifies Stellar payment claims from the ledger, not from screenshots.
The output is a sealed evidence bundle with a verdict: VERIFIED, NOT_VERIFIED,
or INSUFFICIENT_EVIDENCE. The system is deterministic, tamper-evident, and
makes no claim beyond what the ledger can establish.

## Invariants (enforced, not aspirational)

### 1. No float in the decision path

Amounts are integer stroops (1 unit = 10^7 stroops). Stellar Horizon returns
decimal strings; we convert with `Decimal` (exact) and store as `int`. No
float ever enters a `PaymentClaim`, `PaymentEvidence`, or the sealed payload.

**Violation indicator:** any `float` in `amount_stroops`, any `float()` call
in the adjudication or sealing path.

### 2. The seal covers the payload, not the metadata

The SHA-256 seal is computed over `{version, claim, evidence, checks, verdict,
scope_notes}`. The `chain_of_custody` dict (including `fetched_at`) lives
outside the seal. This means the timestamp of retrieval can change without
invalidating the seal — but changing any fact the verdict rests on breaks it.

**Violation indicator:** `chain_of_custody` appearing inside `sealed_payload`.

### 3. Three verdicts, not two

- `VERIFIED` — all applicable checks PASS
- `NOT_VERIFIED` — at least one check FAIL
- `INSUFFICIENT_EVIDENCE` — transaction not found or extraction failed

`INSUFFICIENT_EVIDENCE` is not the same as `NOT_VERIFIED`: the former means
we could not look, the latter means we looked and the claim does not hold.

**Violation indicator:** collapsing INSUFFICIENT_EVIDENCE into NOT_VERIFIED,
or returning VERIFIED when any check failed.

### 4. ABSTAIN is not PASS

A field not present in the claim (None) is ABSTAIN-ed, not assumed true. An
empty claim (only tx hash) can still verify — but it only verifies that the
transaction exists and is successful, nothing more.

**Violation indicator:** treating None as "match anything" instead of
"not checked."

### 5. Fail closed

If anything goes wrong — transaction not found, extraction error, network
failure — the engine returns INSUFFICIENT_EVIDENCE, never VERIFIED.

**Violation indicator:** any path that returns VERIFIED after an error.

### 6. Scope notes are always present

Every bundle includes three scope notes reminding the user what PROOF does
NOT prove:
- Payment execution does not establish legal satisfaction of any underlying debt.
- Transaction existence does not establish delivery of goods or services.
- Wallet signature does not establish human identity.

**Violation indicator:** a bundle without scope notes.

## Build and test

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Architecture

```
proof/
  canonicalize.py    # typed, ordered, versioned serialization + SHA-256 seal
  claim.py           # PaymentClaim — what someone asserts happened (incl. commitment_tx_hash)
  commitment.py      # CommitmentTerms, PaymentCommitment, Receipt — on-chain commitments
  commitment_extractor.py  # extract commitment from manage_data operations
  dispute.py         # DisputeResult, adjudicate_dispute, find_contradictions — L5 disputes
  evidence.py        # PaymentEvidence, PaymentOperation, CheckResult, EvidenceBundle
  stellar_client.py  # Horizon API wrapper (testnet + mainnet, fetches tx/ops/effects)
  extractor.py       # reconstruct evidence from tx + operations + effects (L3: multi-op, path payments)
  adjudicator.py     # compare claim vs evidence (+ optional commitment), produce checks + verdict
  verifier.py        # independent stdlib-only bundle verifier
  engine.py          # main entry points: verify_payment, verify_dispute, issue_receipt
```

## Commit conventions

- Commit messages in English, describing *why* not *what*.
- No `rebase`, `squash`, or `force-push` in agent sessions.
- Tag a restore point before each session:
  `git tag -a "pre-session-$(date +%Y%m%d-%H%M%S)" -m "restore point"`
