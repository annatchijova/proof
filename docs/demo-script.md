# PROOF live demo script

Target length: 2–3 minutes. The demo shows three observable outcomes from one
real Stellar Testnet example and does not depend on a funded identity or on
writing to the chain. The frozen scope is defined in
[`checkpoint-2-scope.md`](checkpoint-2-scope.md).

## Before the room

1. Open the deployed UI:
   `https://proof-api-1028999311218.us-central1.run.app`.
2. Confirm the page loads and click the verified Testnet example once.
3. Do not type or display seed phrases, private keys, or credentials.

## Live sequence

### 0:00 — Problem

Say: “A screenshot can claim that someone paid, but it is not the payment
record. PROOF checks the claim against the public Stellar ledger.”

### 0:20 — Load the real payment

Click “Payment that matches the claim → VERIFIED”. Say: “This is a real
Stellar Testnet transaction. The transaction stays fixed; I am checking the
claim against it.”

### 0:35 — VERIFIED

Click “Verify Payment”. Wait for the response. Point in this order:

1. individual checks;
2. `VERIFIED` verdict;
3. sealed evidence bundle and SHA-256 seal.

Say: “The ledger supports every asserted property, so PROOF returns
`VERIFIED`. I will show the checks and the ledger number, not just the label.”

### 1:10 — NOT_VERIFIED

Click “Payment that contradicts the ledger → NOT_VERIFIED”, or change the
amount from `100` to `200` while leaving the transaction hash unchanged.

Click “Verify Payment”. Point at the failed amount check.

Say: “The transaction is unchanged. I changed only the claimed amount. The
ledger was found, but the claim no longer matches it: `NOT_VERIFIED`.”

### 1:45 — INSUFFICIENT_EVIDENCE, only if time allows

Click “Transaction that cannot be found → INSUFFICIENT_EVIDENCE”. Say: “This
one means PROOF could not establish enough evidence. It is deliberately not
collapsed into `NOT_VERIFIED`.”

### 2:15 — Stellar and close

Say: “Stellar is necessary here because it is the public source of the payment
facts that PROOF checks. PROOF verifies what the ledger establishes; it does
not prove delivery, debt satisfaction, or human identity.”

## Recovery rules

- If the first request is slow, wait once; do not submit repeatedly.
- If the API returns an error, read the specific error and state that the
  result is not evidence of a payment.
- If the UI shows a stale result after loading another example, reload before
  continuing; never present a stale verdict as the new claim's result.
- If asked whether PROOF proves delivery, legal satisfaction, or human
  identity, answer “No; those are outside the ledger evidence scope.”
