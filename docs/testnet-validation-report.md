# Testnet Validation Report — PROOF

Date: 2026-09-23
Network: Stellar Testnet (Test SDF Network ; September 2015)
Contract ID: `CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I`

> Historical execution record. This report documents a complete payment →
> Soroban commitment/receipt run using payment transaction `dde823...` at
> ledger `4821041`. It is separate from the current Checkpoint 2 UI example,
> which uses payment transaction `0ef764...` at ledger `4821215` for the public
> read-only demo. The two executions have different claims, seals, and ledger
> records; neither is presented as metadata for the other.

For the current Checkpoint 2 execution, the public deployment also exposes
the matching read-only Soroban records for reference `INV-TEST-129650` and
payment `0ef764...`: commitment ledger `4821217` and receipt ledger `4821218`,
with receipt verdict `VERIFIED` and seal
`c6d21734805d59886bc9a629893eb108a0666c74a03ed6e19e5abdc50e1b7d51`. Those
records are cited by the current UI; the detailed command transcript below
remains the historical `dde823...` run.

---

## 1. Testnet paths actually executed

### Path A — Verification path

```
real Testnet tx → Horizon acquisition → evidence extraction → adjudication
→ sealed EvidenceBundle → independent verification → tamper detection
```

Validated end-to-end with a real transaction submitted to Testnet.

### Path B — Soroban commitment path

```
sealed EvidenceBundle → commitment hash → Soroban contract on Testnet
→ retrieve commitment → retrieve receipt → verify temporal order
→ independently verify bundle against on-chain commitment
```

Validated end-to-end against the deployed Soroban contract.

---

## 2. Transaction hashes and ledger references

| Item | Value |
|---|---|
| Payment tx hash | `dde823c73034e88525f2d1d5151f345077194e49f680c4514242fba612d95fc5` |
| Payment ledger | 4821041 |
| Commitment registration ledger | 4821043 |
| Receipt registration ledger | 4821045 |
| Commitment hash | `19ece8925437b93cfdc9664c3af208c5cfd2d0ce20cfb6ff4a9b6fc6a12e2a2a` |
| Evidence bundle seal | `55717b0034c5cd0102b8d6cecd5c0120b8cac72419a37a77b059adc59b0fde01` |
| Verdict | VERIFIED |

### Commands to independently inspect

```bash
# Inspect the payment transaction on Horizon
curl -s 'https://horizon-testnet.stellar.org/transactions/dde823c73034e88525f2d1d5151f345077194e49f680c4514242fba612d95fc5' | python3 -m json.tool

# Retrieve the commitment from the Soroban contract
stellar contract invoke --source alice --network testnet \
  --id CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I \
  -- get_commitment --reference INV-TEST-184

# Retrieve the receipt from the Soroban contract
stellar contract invoke --source alice --network testnet \
  --id CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I \
  -- get_receipt --transaction_hash dde823c73034e88525f2d1d5151f345077194e49f680c4514242fba612d95fc5

# Verify temporal order on-chain
stellar contract invoke --source alice --network testnet \
  --id CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I \
  -- verify_temporal_order --reference INV-TEST-184 \
  --transaction_hash dde823c73034e88525f2d1d5151f345077194e49f680c4514242fba612d95fc5
```

---

## 3. Deployed contract ID

```
CDY3VWVDMRNMPGENYV4BCVNVVGLUWF76TQTSOJOOBOPG4XXLTEH7NT4I
```

Deployed via `stellar contract deploy` with source account `alice`
(`GDS44XQB6ATLPTIZMF3QLC5JQ4TAA7ECFK7UPR3GYDOZBRXRSA7GKOCH`).

Deploy transactions:
- WASM upload: `27e2e5030ae9d22df7ebb257d226ff767a803051a6ca5b9d8cf939051f6286ff`
- Contract creation: `0e508b3f41e805e0be5aebf8437952d59edb77dfa7fef072335525410af33a13`

---

## 4. Contract interface

```rust
// Commitments
register_commitment(env, committer: Address, reference: String, commitment_hash: BytesN<32>) -> Commitment
get_commitment(env, reference: String) -> Option<Commitment>
list_commitments(env) -> Vec<String>

// Receipts
register_receipt(env, registrar: Address, transaction_hash: String, seal: BytesN<32>, verdict: String) -> Receipt
get_receipt(env, transaction_hash: String) -> Option<Receipt>
list_receipts(env) -> Vec<String>

// Temporal verification
verify_temporal_order(env, reference: String, transaction_hash: String) -> u32
// Returns: 0=commitment missing, 1=receipt missing, 2=wrong order, 3=correct order
```

---

## 5. Observed Horizon/RPC divergences

**No divergences found.** The actual Horizon response fields match the
fixtures exactly:

| Field | Fixture | Real Horizon | Match |
|---|---|---|---|
| `hash` | string | string | Yes |
| `ledger` | int | int | Yes |
| `created_at` | ISO 8601 string | ISO 8601 string | Yes |
| `successful` | bool | bool | Yes |
| `memo` | string/null | string/null | Yes |
| `memo_type` | string | string | Yes |
| `type` (op) | string | string | Yes |
| `funder` (create_account) | string | string | Yes |
| `account` (create_account) | string | string | Yes |
| `starting_balance` | string | string | Yes |
| `from` (payment) | string | string | Yes |
| `to` (payment) | string | string | Yes |
| `amount` (payment) | string | string | Yes |

The real response includes additional fields (`fee_paid`, `source_account`,
`operation_count`, `id`) that the extractor does not read. These are
ignored, not used — no silent assumptions.

---

## 6. Fixes required

No code fixes were required for the Testnet validation. The existing
implementation worked correctly against real Horizon responses and the
real Soroban contract.

**One CLI behavior noted (not a code fix):** The stellar CLI v28 uses
"root" auth mode by default, which automatically authorizes all addresses
in the transaction. This is a CLI convenience, not a contract security
issue. In a production deployment with independent signatures, the
contract's `require_auth()` enforces that only the committer can register
a commitment. This should be documented for deployers.

---

## 7. Full test results

### Python suite

```
161 passed, 0 skipped, 1 warning in 7.00s
```

All tests pass, including adversarial tests against real Testnet:
- Correct claim → VERIFIED
- Wrong recipient → NOT_VERIFIED
- Wrong amount → NOT_VERIFIED
- Nonexistent tx → INSUFFICIENT_EVIDENCE
- Tamper detection after sealing

### Rust suite

```
8 passed; 0 failed
```

### Soroban contract on Testnet

| Test | Expected | Result |
|---|---|---|
| Register commitment | Success | Success (ledger 4821043) |
| Retrieve commitment | Returns commitment | Returns correct hash, committer, ledger |
| Register receipt | Success | Success (ledger 4821045) |
| Retrieve receipt | Returns receipt | Returns correct seal, verdict, ledger |
| Verify temporal order | 3 (correct) | 3 |
| Duplicate commitment | Fail (panic) | Fail (InvalidAction) |
| Unknown commitment | null | null |
| Unknown receipt | null | null |
| Temporal order (unknown) | 0 | 0 |
| List commitments | ["INV-TEST-184"] | ["INV-TEST-184"] |
| List receipts | [tx_hash] | [tx_hash] |

---

## 8. Exact Soroban security/evidence property

### What the contract proves

1. **Commitment existence with attribution:** A specific commitment hash
   was registered on-chain at a specific ledger by a specific account.
   The commitment is immutable — it cannot be overwritten.

2. **Receipt existence with attribution:** A specific evidence bundle
   seal was registered on-chain at a specific ledger. The receipt is
   immutable.

3. **Temporal order:** The commitment was registered at an earlier
   ledger than the receipt. This proves the terms were committed
   *before* the receipt was issued.

### What the contract does NOT prove

1. **The payment is true.** The contract stores a hash, not the terms.
   It does not verify that the payment happened or that the terms are
   correct. That is the off-chain core's job.

2. **The committed terms are true.** The contract stores a hash of the
   terms, not the terms themselves. Anyone can commit any hash. The
   off-chain core must independently verify that the committed hash
   matches the actual payment evidence.

3. **The seal corresponds to a valid verification.** The contract stores
   a seal, not the evidence. The off-chain verifier must independently
   recompute the seal and confirm the bundle was not tampered.

4. **The committer is authorized to commit.** The contract uses
   `require_auth()` to ensure the committer signed the transaction,
   but does not verify that the committer is authorized by any
   real-world authority to make the commitment.

### The critical boundary

**"Commitment exists on-chain" does NOT mean "payment claim is true."**

The contract proves that a hash was committed at a specific time by a
specific account. The off-chain core proves that the payment actually
happened and matches the committed terms. Both are needed:
- Without the contract, there is no on-chain evidence that the terms
  were committed before the payment.
- Without the off-chain core, there is no evidence that the payment
  actually happened or matches the committed terms.

---

## 9. Recommendation for manage_data

### Current state

PROOF has two commitment mechanisms:

1. **manage_data (L4):** Uses native Stellar `manage_data` operations
   to store commitment hashes and receipt seals as key-value pairs.
   Keys: `PROOF:COMMIT:<reference>` and `PROOF:RECEIPT:<tx_hash>`.

2. **Soroban contract (L4+):** A dedicated smart contract that stores
   commitments and receipts with `require_auth()`, immutability
   enforcement, and temporal order verification.

### Recommendation: Soroban replaces manage_data for new commitments

**Rationale:**

- The Soroban contract provides strictly stronger properties:
  `require_auth()`, enforced immutability (panic on overwrite), and
  temporal order verification — all on-chain.
- manage_data provides none of these: any account can write any key,
  keys can be overwritten, and there is no temporal order check.
- Maintaining two systems creates confusion about which is
  authoritative and increases the attack surface.

**Migration plan:**

1. The Soroban contract becomes the primary commitment mechanism.
2. `manage_data` is retained as a deliberately supported alternative
   for cases where Soroban is not available (e.g., pre-Soroban accounts,
   simple integrations).
3. The off-chain core treats both as valid commitment sources.
4. Documentation clearly states that Soroban is the recommended path
   and manage_data is a fallback.

**Why not keep both with distinct responsibilities:**

Both mechanisms serve the same purpose: storing commitment hashes and
receipt seals on-chain. They do not have distinct responsibilities —
they are redundant. Keeping both active without clear guidance creates
ambiguity about which is authoritative.

**Why not keep manage_data only:**

manage_data lacks `require_auth()`, enforced immutability, and temporal
order verification. The Soroban contract provides all three. For a
product whose value proposition is verifiable evidence, the stronger
mechanism should be primary.

---

## 10. Historical follow-up items

This section records the state at the time of this historical report. The
public deployment and Soroban API wiring were completed subsequently and are
documented in the current README and `TECHNICAL.md`.

1. **Rate limiting / auth:** The API has no authentication or rate
   limiting. For a public demo, this should be behind a gateway or
   have basic rate limiting. Documented as F7 in the red team review.

2. **Testnet reliability:** Testnet transactions may be pruned. The
   adversarial tests handle this by skipping if the tx is not found,
   but a public demo should use a freshly submitted tx or a stable
   testnet account.
