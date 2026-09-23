# proof-registry — Soroban contract for PROOF

A tamper-evident on-chain registry for PROOF commitments and receipts.

## What the contract does

The contract stores two types of records:

- **Commitments**: a reference (e.g. invoice number) mapped to a commitment hash
  (SHA-256 of the canonical payment terms). Registered before a payment occurs.
- **Receipts**: a transaction hash mapped to a seal (SHA-256 of the evidence
  bundle). Registered after a payment is verified.

The contract also provides a `verify_temporal_order` function that checks
whether a commitment was registered before a receipt (on-chain temporal order
verification).

## What the contract does NOT do

- **Does not verify payments.** All verification logic lives in the off-chain
  Python core. The contract is a registry, not an adjudicator.
- **Does not compute hashes.** The commitment hash and receipt seal are
  computed off-chain and passed to the contract as `BytesN<32>`.
- **Does not prove the committed terms are true.** Only that they were
  committed at a specific ledger by a specific account.
- **Does not prove the seal corresponds to a valid verification.** Only that
  it was stored.

## Immutability

Commitments and receipts are immutable once registered. Attempting to
overwrite an existing record panics. This is a deliberate design choice:
a commitment or receipt that could be silently overwritten would not be
tamper-evident.

## Authorization

- `register_commitment` requires the committer to authorize the call.
- `register_receipt` requires the registrar to authorize the call.
- Read operations (`get_commitment`, `get_receipt`, `verify_temporal_order`,
  `list_commitments`, `list_receipts`) do not require authorization.

## API

| Function | Description |
|---|---|
| `register_commitment(committer, reference, commitment_hash)` | Register a commitment |
| `register_receipt(registrar, transaction_hash, seal, verdict)` | Register a receipt |
| `get_commitment(reference)` | Query a commitment by reference |
| `get_receipt(transaction_hash)` | Query a receipt by transaction hash |
| `verify_temporal_order(reference, transaction_hash)` | Check temporal order (0=missing commitment, 1=missing receipt, 2=wrong order, 3=success) |
| `list_commitments()` | List all commitment references |
| `list_receipts()` | List all receipt transaction hashes |

## Build

```bash
cargo build --target wasm32v1-none --release
```

## Test

```bash
cargo test
```

## Integration with the Python core

The Python core (L4) currently uses `manage_data` operations for on-chain
commitments. This Soroban contract provides a more structured alternative:
persistent storage, typed records, authorization, and queryable state.

Future integration: the Python core will be extended to optionally use this
contract instead of `manage_data` for commitment and receipt storage. The
contract extends the evidence model — it does not duplicate off-chain logic.
