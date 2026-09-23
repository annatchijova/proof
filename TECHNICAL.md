# PROOF — Technical README

Architecture, threat model, design decisions, and invariants.

## Architecture

```
PaymentClaim (transaction_hash + optional assertions)
    |
    v
StellarClient.fetch_transaction() --- Horizon API (testnet/mainnet)
StellarClient.fetch_operations()
    |
    v
extractor.extract_evidence() --- validate + reconstruct PaymentEvidence
    |
    v
adjudicator.adjudicate() --- compare each claim proposition vs evidence
    |
    v
adjudicator.compute_verdict() --- VERIFIED / NOT_VERIFIED / INSUFFICIENT
    |
    v
EvidenceBundle.build() --- canonicalize + SHA-256 seal
    |
    v
verifier.verify_bundle() --- independent re-seal + consistency check
```

## Data model

### PaymentClaim

What someone asserts happened. Every field is optional except
`transaction_hash`. Fields left as `None` are not checked (ABSTAIN).

| Field | Type | Description |
|---|---|---|
| `transaction_hash` | `str` | 64-char hex hash (required) |
| `sender` | `str \| None` | Stellar address (G...) |
| `recipient` | `str \| None` | Stellar address (G...) |
| `asset_code` | `str \| None` | e.g., "XLM", "USDC" |
| `asset_issuer` | `str \| None` | Issuer address (G...) |
| `amount_stroops` | `int \| None` | Amount in stroops (integer) |
| `reference` | `str \| None` | Memo/reference text |
| `ledger_min` | `int \| None` | Earliest acceptable ledger |
| `ledger_max` | `int \| None` | Latest acceptable ledger |

### PaymentEvidence

What the ledger shows. All fields are populated from the Horizon API
response, validated at the boundary.

| Field | Type | Description |
|---|---|---|
| `transaction_hash` | `str` | 64-char hex hash |
| `ledger` | `int` | Ledger sequence number |
| `timestamp_unix` | `int` | Unix timestamp (seconds) |
| `successful` | `bool` | Whether the tx succeeded |
| `sender` | `str` | Source address |
| `recipient` | `str` | Destination address |
| `asset_code` | `str` | "XLM" or custom code |
| `asset_issuer` | `str \| None` | None for native XLM |
| `amount_stroops` | `int` | Amount in stroops |
| `memo` | `str \| None` | Transaction memo |
| `operation_type` | `str` | "payment", "create_account", etc. |

### EvidenceBundle

The sealed output. The `sealed_payload` (version, claim, evidence, checks,
verdict, scope_notes) is what gets hashed. The `chain_of_custody` is
metadata stored beside the seal, not inside it.

## Canonical serialization

The canonicalizer (`canonicalize.py`) is the single source of truth for
deterministic serialization. Properties:

- **Typed:** `bool` is checked before `int` (bool subclasses int in Python).
  `True` becomes `"true"`, `1` becomes `"1:int"`, `"1"` stays `"1"`. These
  never collide.
- **Ordered:** dict keys are sorted recursively. Dict insertion order
  never leaks into the bytes.
- **Versioned:** `CANONICALIZE_VERSION = "1"` is stamped into every sealed
  payload. When the schema changes, the version is bumped and old verifiers
  keep working.

The seal is `SHA-256(canonical_bytes(payload))` where `canonical_bytes`
produces `json.dumps(canonicalize(payload), sort_keys=True, ensure_ascii=False)`.

## Determinism guarantees

- No float in any sealed value. Amounts are integer stroops.
- No timestamp inside the sealed payload. `fetched_at` is in
  `chain_of_custody`, outside the seal.
- No dict ordering dependence. Keys are sorted recursively.
- No set iteration. No `PYTHONHASHSEED` dependence.
- The same claim + evidence always produces the same seal. Verified by
  `test_determinism.py` (5 runs, identical seals).

## Threat model

**Attacker CAN:**
- Submit any string as a transaction hash.
- Submit any claim with any values (valid format, arbitrary content).
- Choose the network (testnet or mainnet).

**Attacker CANNOT:**
- Modify the Stellar ledger.
- Forge a transaction hash (SHA-256 preimage resistance).
- Alter Horizon API responses in transit (TLS).
- Control the PROOF execution environment.

**Trust boundaries:**
1. **Input boundary** — `PaymentClaim.__post_init__` validates every field.
   Invalid hashes, addresses, amounts, and ledger ranges are rejected
   before any processing.
2. **Horizon API boundary** — external data source. Responses are trusted
   only as much as the TLS connection to Horizon. The extractor validates
   every field from the response.
3. **Sealing boundary** — the canonical serialization and SHA-256 seal are
   the integrity guarantee. The verifier recomputes the seal independently.

## Security properties

- **Fail closed:** any error (tx not found, extraction failure, network
  error) returns `INSUFFICIENT_EVIDENCE`, never `VERIFIED`.
- **No ambient authority:** the Stellar client receives the network
  parameter explicitly; no global state.
- **Bound everything:** stroops are bounded by `MAX_STROOPS` (2^63 - 1).
  Ledger sequences are non-negative. Addresses are format-validated.
- **Idempotent:** the same claim + network always produces the same verdict
  and seal (given the same ledger state).

## Design decisions

### Why integer stroops, not decimal amounts?

Stellar amounts are signed 64-bit integers in stroops. Horizon returns them
as decimal strings ("100.0000000"). Converting to `int` via `Decimal`
(exact arithmetic) preserves the integer nature. Float would introduce
ordering- and platform-dependent rounding — a determinism defect.

### Why ABSTAIN instead of "match anything" for unspecified fields?

A claim that doesn't specify a recipient should not be treated as "any
recipient is fine." ABSTAIN makes this explicit: "this proposition was not
asserted, so it was not checked." The scope notes remind the user what
PROOF does not prove.

### Why three verdicts, not two?

`INSUFFICIENT_EVIDENCE` (could not look) is semantically distinct from
`NOT_VERIFIED` (looked and the claim does not hold). Collapsing them
would hide the difference between "the transaction doesn't exist" and
"the transaction exists but doesn't match the claim."

### Why is chain_of_custody outside the seal?

The `fetched_at` timestamp changes every time you query Horizon. If it
were inside the seal, re-verifying a bundle would fail because the
timestamp differs. The seal covers the facts (claim, evidence, checks,
verdict); the metadata (when it was fetched, from where, with what tool
version) lives beside it.

### Why an independent verifier?

A verifier that imports the producer's logic can inherit the producer's
bug. `verifier.py` uses only `hashlib`, `json`, and `canonicalize` — it
does not import the engine, the extractor, or the adjudicator. It
recomputes the seal from the bundle's fields and checks consistency.

## Supported operation types

| Type | L3 support | Notes |
|---|---|---|
| `payment` | Full | Single-asset transfer |
| `create_account` | Full | XLM, amount from starting_balance |
| `path_payment_strict_receive` | Full | Source + destination assets, both amounts |
| `path_payment_strict_send` | Full | Source + destination assets, both amounts |
| `account_merge` | Full | Amount from effects (account_debited) |

## Multi-operation transactions

L3 extracts ALL payment-type operations from a transaction, not just the
first. Each operation is represented as a `PaymentOperation` in the
`operations` list. The top-level fields (`sender`, `recipient`, `asset_code`,
etc.) are convenience aliases for the first operation, preserving backward
compatibility with L1/L2 callers.

## Memo types

L3 classifies memos into four types: `text`, `hash`, `return`, `none`.
Reference matching only compares the claim's `reference` against the memo
when `memo_type` is `text`. Hash and return memos are binary and don't have
a string representation that a claim's reference field would match
meaningfully — those produce ABSTAIN.

## Known limitations (L3)

- **Source asset claims:** the `PaymentClaim` does not yet have a
  `source_asset_code` field. Path payment source assets are extracted and
  reported in the evidence, but the adjudicator ABSTAINs on source asset
  matching. Adding source asset assertions to claims is L4.
- **No on-chain receipts:** L4 will add Stellar contract-based receipt
  registration.
- **No API/MCP server:** L6 will expose verification as an API.

## Falsifiers

- **Determinism claim:** if two runs of the same claim + evidence produce
  different seals, the determinism invariant is violated. Test:
  `test_determinism.py::test_seal_is_deterministic_across_runs`.
- **Tamper detection:** if modifying any sealed field does not break the
  seal, the integrity guarantee is violated. Tests:
  `test_verifier.py::test_tampered_*`.
- **Fail closed:** if any error path returns VERIFIED, the security
  invariant is violated. Test: `test_adjudicator.py::test_failed_*`.
